# Cloud Formation Troposphere template for Alchemy Cluster

from troposphere import Base64, FindInMap, GetAtt, Join, Output
from troposphere import Parameter, Ref, Tags, Template

from troposphere.cloudformation import Init

from troposphere.autoscaling import AutoScalingGroup
from troposphere.autoscaling import LaunchConfiguration

from troposphere.ec2 import SubnetNetworkAclAssociation
from troposphere.ec2 import RouteTable
from troposphere.ec2 import Instance, NetworkInterfaceProperty
from troposphere.ec2 import SubnetRouteTableAssociation
from troposphere.ec2 import NetworkAclEntry
from troposphere.ec2 import VPCGatewayAttachment
from troposphere.ec2 import Subnet
from troposphere.ec2 import SecurityGroup
from troposphere.ec2 import EIP
from troposphere.ec2 import Route
from troposphere.ec2 import EIPAssociation
from troposphere.ec2 import InternetGateway
from troposphere.ec2 import VPC
from troposphere.ec2 import NetworkAcl
from troposphere.ec2 import BlockDeviceMapping
from troposphere.ec2 import EBSBlockDevice

from troposphere.elasticloadbalancing import LoadBalancer


t = Template()

###     Meta Data     ###
t.add_version("2010-09-09")

t.add_description("""
Alchemy Cluster with an Autoscaling CoreOS Cluster and an Elastic Load Balancer.
""")

###     End Of Meta Data     ###


###     Mappings    ###
# copied from  https://s3.amazonaws.com/coreos.com/dist/aws/coreos-stable-hvm.template
t.add_mapping("CoreOSImageRegionMap", {
  "eu-central-1" : {
    "AMI" : "ami-15190379"
  },

  "ap-northeast-1" : {
    "AMI" : "ami-02c9c86c"
  },

  "us-gov-west-1" : {
    "AMI" : "ami-e0b70b81"
  },

  "sa-east-1" : {
    "AMI" : "ami-c40784a8"
  },

  "ap-southeast-2" : {
    "AMI" : "ami-949abdf7"
  },

  "ap-southeast-1" : {
    "AMI" : "ami-00a06963"
  },

  "us-east-1" : {
    "AMI" : "ami-7f3a0b15"
  },

  "us-west-2" : {
    "AMI" : "ami-4f00e32f"
  },

  "us-west-1" : {
    "AMI" : "ami-a8aedfc8"
  },

  "eu-west-1" : {
    "AMI" : "ami-2a1fad59"
  }
})

t.add_mapping("NatRegionMap",
{u'ap-northeast-1': {u'AMI': u'ami-27d6e626'},
 u'ap-southeast-1': {u'AMI': u'ami-6aa38238'},
 u'ap-southeast-2': {u'AMI': u'ami-893f53b3'},
 u'eu-central-1': {u'AMI': u'ami-ae380eb3'},
 u'eu-west-1': {u'AMI': u'ami-14913f63'},
 u'sa-east-1': {u'AMI': u'ami-8122969c'},
 u'us-east-1': {u'AMI': u'ami-184dc970'},
 u'us-west-1': {u'AMI': u'ami-a98396ec'},
 u'us-west-2': {u'AMI': u'ami-290f4119'}}
)

###     End Of Mappings    ###

###     Setup Parameters Used


SecurityKeyName = t.add_parameter(Parameter(
    "SecurityKeyName",
    ConstraintDescription="must be the name of an existing EC2 KeyPair.",
    Type="AWS::EC2::KeyPair::KeyName",
    Description="Name of an existing EC2 KeyPair to enable SSH access to the instances",
))

ClusterName = t.add_parameter(Parameter(
    "ClusterName",
    Type="String",
    Description="Unique Name for the cluster",
))

CoreOSDiscoveryURL = t.add_parameter(Parameter(
    "CoreOSDiscoveryURL",
    Type="String",
    Description="An unique etcd cluster discovery URL. Grab a new token from https://discovery.etcd.io/new?size=3",
))

AutoScalingSize = t.add_parameter(Parameter(
    "AutoScalingSize",
    Type="Number",
    Description="the number of instances to launch in the AutoScalaing Group",
    Default="3"
))

AutoScalingGroupInstanceType = t.add_parameter(Parameter(
    "AutoScalingGroupInstanceType",
    Default="m3.medium",
    ConstraintDescription="must be a valid EC2 instance type.",
    Type="String",
    Description="Cluster EC2 instance type",
    AllowedValues=["m3.medium", "m3.large", "m3.xlarge", "m3.2xlarge", "c4.large", "c4.xlarge", "c4.2xlarge", "c4.4xlarge", "c4.8xlarge", "g2.2xlarge", "r3.large", "r3.xlarge", "r3.2xlarge", "r3.4xlarge", "r3.8xlarge"],
))


###      SETUP THE VPC         ###

AlchemyVPC = t.add_resource(VPC(
    "AlchemyVPC",
    EnableDnsSupport="true",
    EnableDnsHostnames="false",
    CidrBlock="10.0.0.0/16",
    Tags=Tags(Name=Join("",[Ref(ClusterName), " VPC"]))
))


### Internet Gateway
internetGateway = t.add_resource(InternetGateway(
    "internetGateway",
    Tags=Tags(Name=Join("",[Ref(ClusterName), " Internet Gateway"]))
))

internetGatewayAttachment = t.add_resource(VPCGatewayAttachment(
    "internetGatewayAttachment",
    VpcId=Ref(AlchemyVPC),
    InternetGatewayId=Ref(internetGateway),
))

### ACLS

alchemyACL = t.add_resource(NetworkAcl(
    "alchemyACL",
    VpcId=Ref(AlchemyVPC)
))

aclEntry1 = t.add_resource(NetworkAclEntry(
    "aclEntry1",
    NetworkAclId=Ref(alchemyACL),
    RuleNumber="100",
    Protocol="-1",
    Egress="true",
    RuleAction="allow",
    CidrBlock="0.0.0.0/0"
))

aclEntry2 = t.add_resource(NetworkAclEntry(
    "aclEntry2",
    Protocol="-1",
    Egress="false",
    RuleNumber="100",
    CidrBlock="0.0.0.0/0",
    RuleAction="allow",
    NetworkAclId=Ref(alchemyACL)
))



### ROUTING TABLES

publicRouteTable = t.add_resource(RouteTable(
    "publicRouteTable",
    VpcId=Ref(AlchemyVPC),
    Tags=Tags(Name=Join("",[Ref(ClusterName), " Public Route Table"]))
))

privateRouteTable = t.add_resource(RouteTable(
    "privateRouteTable",
    VpcId=Ref(AlchemyVPC),
    Tags=Tags(Name=Join("",[Ref(ClusterName), " Private Route Table"]))
))


privateInternetRoute = t.add_resource(Route(
    "privateInternetRoute",
    InstanceId=Ref("natProxyEC2Instance"), #Ugly circular reference
    DestinationCidrBlock="0.0.0.0/0",
    RouteTableId=Ref(privateRouteTable)
))

publicInternetRoute = t.add_resource(Route(
    "publicInternetRoute",
    GatewayId=Ref(internetGateway),
    DestinationCidrBlock="0.0.0.0/0",
    RouteTableId=Ref(publicRouteTable),
    DependsOn="internetGatewayAttachment",
))



### SUBNETS

publicASubnet = t.add_resource(Subnet(
    "publicASubnet",
    VpcId=Ref(AlchemyVPC),
    AvailabilityZone = Join("", [Ref("AWS::Region"),"a"]),
    CidrBlock="10.0.254.0/24",
    Tags=Tags(Name=Join("",[Ref(ClusterName), " Public A Subnet"]))
))

publicBSubnet = t.add_resource(Subnet(
    "publicBSubnet",
    VpcId=Ref(AlchemyVPC),
    AvailabilityZone=Join("", [Ref("AWS::Region"),"b"]),
    CidrBlock="10.0.253.0/24",
    Tags=Tags(Name=Join("",[Ref(ClusterName), " Public B Subnet"]))
))


privateASubnet = t.add_resource(Subnet(
    "privateASubnet",
    VpcId=Ref(AlchemyVPC),
    AvailabilityZone=Join("", [Ref("AWS::Region"),"a"]),
    CidrBlock="10.0.1.0/24",
    Tags=Tags(Name=Join("",[Ref(ClusterName), " Private A Subnet"]))
))

privateBSubnet = t.add_resource(Subnet(
    "privateBSubnet",
    VpcId=Ref(AlchemyVPC),
    AvailabilityZone=Join("", [Ref("AWS::Region"),"b"]),
    CidrBlock="10.0.2.0/24",
    Tags=Tags(Name=Join("",[Ref(ClusterName), " Private B Subnet"]))
))

### Add ACLS to Subnets

privateBSubnetACLAttachment = t.add_resource(SubnetNetworkAclAssociation(
    "privateBSubnetACLAttachment",
    SubnetId=Ref(privateBSubnet),
    NetworkAclId=Ref(alchemyACL),
))

privateASubnetACLAttachment = t.add_resource(SubnetNetworkAclAssociation(
    "privateASubnetACLAttachment",
    SubnetId=Ref(privateASubnet),
    NetworkAclId=Ref(alchemyACL),
))

publicBSubnetACLAttachment = t.add_resource(SubnetNetworkAclAssociation(
    "publicBSubnetACLAttachment",
    SubnetId=Ref(publicBSubnet),
    NetworkAclId=Ref(alchemyACL),
))

publicASubnetACLAttachment = t.add_resource(SubnetNetworkAclAssociation(
    "publicASubnetACLAttachment",
    SubnetId=Ref(publicASubnet),
    NetworkAclId=Ref(alchemyACL),
))


### add route tables to subnets

publicBSubnetRouteTableAttachment = t.add_resource(SubnetRouteTableAssociation(
    "publicBSubnetRouteTableAttachment",
    SubnetId=Ref(publicBSubnet),
    RouteTableId=Ref(publicRouteTable),
))

privateBSubnetRouteTableAttachment = t.add_resource(SubnetRouteTableAssociation(
    "privateBSubnetRouteTableAttachment",
    SubnetId=Ref(privateBSubnet),
    RouteTableId=Ref(privateRouteTable),
))


publicASubnetRouteTableAttachment = t.add_resource(SubnetRouteTableAssociation(
    "publicASubnetRouteTableAttachment",
    SubnetId=Ref(publicASubnet),
    RouteTableId=Ref(publicRouteTable),
))

privateASubnetRouteTableAttachment = t.add_resource(SubnetRouteTableAssociation(
    "privateASubnetRouteTableAttachment",
    SubnetId=Ref(privateASubnet),
    RouteTableId=Ref(privateRouteTable),
))

###      END OF VPC SETUP      ###

###     LOAD BALANCER SETUP    ###

LoadBalancerSecurityGroup = t.add_resource(SecurityGroup(
    "LoadBalancerSecurityGroup",
    SecurityGroupIngress=[
        { "ToPort": "443", "IpProtocol": "tcp", "CidrIp": "0.0.0.0/0", "FromPort": "443" },
        { "ToPort": "80", "IpProtocol": "tcp", "CidrIp": "0.0.0.0/0", "FromPort": "80" }
    ],
    VpcId=Ref(AlchemyVPC),
    GroupDescription="Enable all communication on private subnet",
    SecurityGroupEgress=[{ "ToPort": "8080", "IpProtocol": "tcp", "CidrIp": "0.0.0.0/0", "FromPort": "8080" }],
))

ElasticLoadBalancer = t.add_resource(LoadBalancer(
    "ElasticLoadBalancer",
    Subnets= [Ref(publicASubnet), Ref(publicBSubnet)],
    Listeners=[{
      "InstancePort": "8080",
      "Protocol": "HTTP",
      "InstanceProtocol": "HTTP",
      "LoadBalancerPort": "80"
    }],
    CrossZone="true",
    SecurityGroups=[Ref(LoadBalancerSecurityGroup)],
    Tags=Tags(Name=Join("",[Ref(ClusterName), " ELB"]))
))

###     END OF LOAD BALANCER SETUP    ###

###     AUTO SCALING GROUP SETUP      ###

CoreOSSecurityGroup = t.add_resource(SecurityGroup(
    "CoreOSSecurityGroup",
    SecurityGroupIngress=[{ "ToPort": "65535", "IpProtocol": "-1", "CidrIp": "10.0.0.0/16", "FromPort": "0" }],
    VpcId=Ref(AlchemyVPC),
    GroupDescription="Enable all communication on private subnet",
    SecurityGroupEgress=[{ "ToPort": "65535", "IpProtocol": "-1", "CidrIp": "0.0.0.0/0", "FromPort": "0" }],
))

CoreOSLaunchConfig = t.add_resource(LaunchConfiguration(
    "CoreOSLaunchConfig",
    UserData=Base64(Join("", [
        "#cloud-config\n",
        "coreos:\n",
        "  etcd2:\n",
        "    discovery: ", Ref(CoreOSDiscoveryURL), "\n",
        "    advertise-client-urls: http://$private_ipv4:2379\n",
        "    initial-advertise-peer-urls: http://$private_ipv4:2380\n",
        "    listen-client-urls: http://0.0.0.0:2379\n",
        "    listen-peer-urls: http://$private_ipv4:2380\n",
        "  units:\n",
        "    - name: etcd2.service\n",
        "      command: start\n",
        "    - name: fleet.service\n",
        "      command: start\n",
        "\n",
        "write_files:\n",
        "  - path: /etc/environment\n",
        "    content: |\n",
        "        REGION_NAME=", Ref("AWS::Region"), "\n",
        "        CLUSTER_NAME=", Ref(ClusterName), "\n",
        "        PRIVATEIP=$private_ipv4\n",
        "        PUBLICIP=$public_ipv4\n"
        ]
    )),
    KeyName=Ref(SecurityKeyName),
    SecurityGroups=[Ref(CoreOSSecurityGroup)],
    InstanceType=Ref(AutoScalingGroupInstanceType),
    BlockDeviceMappings=[
      BlockDeviceMapping(
        DeviceName="/dev/xvda",
        Ebs=EBSBlockDevice(VolumeSize="150")
      )
    ],
    ImageId=FindInMap("CoreOSImageRegionMap", Ref("AWS::Region"), "AMI")
))

CoreOSServerAutoScale = t.add_resource(AutoScalingGroup(
    "CoreOSServerAutoScale",
    DesiredCapacity= Ref(AutoScalingSize),
    LoadBalancerNames=[Ref(ElasticLoadBalancer)],
    MinSize=Ref(AutoScalingSize),
    MaxSize=Ref(AutoScalingSize),
    VPCZoneIdentifier=[Ref(privateBSubnet),Ref(privateASubnet)],
    LaunchConfigurationName=Ref(CoreOSLaunchConfig)
))



###     END OF AUTO SCALING GROUP SETUP      ###


###     NAT/SSH TUNNEL SETUP                 ###

NatSecurityGroup = t.add_resource(SecurityGroup(
    "NatSecurityGroup",
    SecurityGroupIngress=[
      { "ToPort": "22", "IpProtocol": "tcp", "CidrIp": "0.0.0.0/0", "FromPort": "22" },
      { "ToPort": "65535", "IpProtocol": "-1", "CidrIp": "10.0.0.0/16", "FromPort": "0" }
    ],
    VpcId=Ref(AlchemyVPC),
    SecurityGroupEgress=[{ "ToPort": "65535", "IpProtocol": "-1", "CidrIp": "0.0.0.0/0", "FromPort": "0" }],
    GroupDescription="Enable all communication on private subnet",
))

natProxyEC2Instance = t.add_resource(Instance(
    "natProxyEC2Instance",
    UserData=Base64(Join("", ["#!/bin/bash\n", "yum update -y && yum install -y yum-cron && chkconfig yum-cron on"])),
    SourceDestCheck="false",
    InstanceType="t2.small",
    ImageId=FindInMap("NatRegionMap", Ref("AWS::Region"), "AMI"),
    KeyName=Ref(SecurityKeyName),
    SubnetId=Ref(publicASubnet),
    SecurityGroupIds=[Ref(NatSecurityGroup)],
    Tags=Tags(Name=Join("",[Ref(ClusterName), " NAT Instance"]))
))

NATIPAddress = t.add_resource(EIP("NATIPAddress", Domain='vpc'))

NATEIPAttachment = t.add_resource(EIPAssociation(
    "NATEIPAttachment",
    InstanceId=Ref(natProxyEC2Instance),
    AllocationId= GetAtt(NATIPAddress, "AllocationId")
))

###     END OF NAT/SSH TUNNEL SETUP                 ###

###     OUTPUT SETUP           ###

ELBURL = t.add_output(Output(
    "ELBURL",
    Description="ELBURL of the website",
    Value=Join("", ["http://", GetAtt(ElasticLoadBalancer, "DNSName")]),
))

NATIPAddress = t.add_output(Output(
    "NATIPAddress",
    Description="Elastic IP address of the NAT",
    Value=Ref(NATIPAddress),
))


###     END OF OUTPUT SETUP       ###


print(t.to_json())
