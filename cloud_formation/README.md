# Using Cloud Formation to Build your Alchemy Platform

## What is Cloud Formation (CF)?

[Cloud Formation](https://aws.amazon.com/cloudformation)(CF) is a declarative way to describe AWS architectures. You create a cloud formation **template** which describes all the required resources and how they are linked, upload it to AWS to create an instance of the template called a **stack**.

If you need to alter the architecture, you can change the template and re-upload it. Cloud Formation will figure out how to alter your stack to fit the new template and then change the stack.

The are many benefits of using Cloud Formation templates as opposed to manually creating resources, including:

1. Setting up an environment by creating a stack is quick and easy. Also, deleting a stack will delete all its resources, leaving your AWS account in a clean state
2. Since creating a stack is quickly repeatable, the architecture itself can be easily tested. Create a stack, run some tests, tear down a stack, repeat.
3. The environment is 100% documented, so new people can find out exactly what is in the cloud by looking at the stacks and the templates.
4. Being documented also means the template can be directly inspected for security risks. By seeing exactly what is running, can make it easier to spot and fix vulnerabilities.
5. Git-Flow architecture. Manage your architecture like you manage code, source repositories, pull requests, and testing the architecture before it is deployed to production.
7. If something goes wrong AWS roll back automatically to the previous state. This means less danger of breaking the architecture and spending many hours investigating.

## What is Troposphere?

Cloud formation templates are written in JSON which can become very large making them difficult to read, document and check for errors. [Troposphere](https://github.com/cloudtools/troposphere) is a python tool and library which allows a template to be defined in python, then output to a JSON template. Troposphere adds basic syntax checking, e.g. making sure you have all the required variables defined, and also lets you add easily readable documentation. This makes working with CF templates a whole lot easier.

To install troposphere use

```
pip install troposphere
```

## alchemy-cluster.py

In this folder is the file `alchemy-cluster.py` which is a troposphere script that can build a CF template with `python alchemy-cluster.py > alchemy-cluster.template`. This template will create a stack that looks like:

```
|--------------------------------------|
|              Public Subnet           |
|  |---------------|   |-------------| |
|  |      ELB      |   |    NAT      | |
|  |---------------|   |-------------| |
|            |                         |
|--------------------------------------|
|           /|\     Private Subnet     |
|          / | \ n * CoreOS instances  |
|  |-------------------------|         |
|  |        Services         |         |
|  |-------------------------|         |
|  |        RabbitMQ         |         |
|  |-------------------------|         |
|  |  Etcd  | Docker | Fleet |         |
|  |-------------------------|         |
|  |        CoreOS           |         |
|  |-------------------------|         |
|--------------------------------------|
```

The infrastructure is made up of a variable number of [CoreOS](https://coreos.com/) instances initialised with a [cloud-config](https://coreos.com/docs/cluster-management/setup/cloudinit-cloud-config/). CoreOS is a barebones GNU/Linux distribution that uses Docker as its mechanism for running applications (i.e. no `apt-get`). Each instance runs the clustering key/value store **etcd** that lets all the instances know about one another and share common information. Fleet uses etcd to store and distribute services defined as [systemd](http://en.wikipedia.org/wiki/Systemd) units.

This example uses the services provided in this project folder `../services` to start RabbitMQ a router, and hello_world services in AWS.

## Working with Cloud Formation and CoreOS

The easiest way to work with CoreOS inside of AWS is to tunnel to an instance through the NAT. This can be accomplished with:

```
export NAT_IP=<the public address of the NAT>
export NODE_IP=<IP address of a Node in the cluster>
ssh -A -N -L 2229:$NODE_IP:22 -L 2379:$NODE_IP:2379 -L 15672:$NODE_IP:15672 ec2-user@$NAT_IP
```


This will open up a tunnel to fleet, etcd, and the RabbitMQ management console.

In a different terminal run:

```
export FLEETCTL_TUNNEL=127.0.0.1:2229 ETCDCTL_ENDPOINT=http://127.0.0.1:2379
```

Then `etcdctl ls` and `fleetctl list-machines` should work.

## Starting the Services

Start the global services with:

```
fleetctl start ../services/zglobal_hosts.service
fleetctl start ../services/zglobal_rabbitmq.service
```

This will start RabbitMQ on all nodes in a cluster. You can check it is running by visiting the management console, that at `http://172.17.8.101:15672/`.

Start the router and two hello world service with:

```
fleetctl start ../services/router_v1.0.1@1
fleetctl start ../services/hello_world_v1.0.1@1
fleetctl start ../services/hello_world_v1.0.1@2
```

This will start one instance of the router and two instances of the hello world service. It is recommended to run multiple instances of the service, and one instance of the router per machine in the cluster.

Now you should be able to curl the ELB with:

```
curl -X GET http://<URL of ELB>/v1/hello
```

## Make it Production Ready

To make this cluster production ready it is recommended to:

1. Add health checks for nodes
2. Add HTTPS support for ELB
3. Have more than 3 instances running across multiple AZs, and have a router running on each

## References

[Fleet video](https://www.youtube.com/watch?v=u91DnN-yaJ8)

[Cloud Formation Best Practices](https://www.youtube.com/watch?v=sAqkN0vIhAY)
