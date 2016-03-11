# Vagrant, CoreOS and Alchemy

Vagrant is a tool to help build a development environment inside a VM.
This configuration uses the Vagrantfile from [coreos-vagrant](https://github.com/coreos/coreos-vagrant) project to create a CoreOS operating system. This can then use the service files, inside of `../services` to start Alchemy services.

CoreOS is a barebones GNU/Linux distribution that uses Docker as its mechanism for running applications (i.e. no `apt-get`). Each instance runs the clustering key/value store **etcd** that lets all the instances know about one another and share common information. Fleet uses etcd to store and distribute services defined as [systemd](http://en.wikipedia.org/wiki/Systemd) units.

In this example we will start two instances of the `hello_world` service, and one instance of the `router` service.

## Vagrant CoreOS on OSX

**More Information at the [coreos-vagrant](https://github.com/coreos/coreos-vagrant) project**

Install vagrant using brew and brew-cask:

```
brew cask install vagrant
```

To build the VM running CoreOS:

```
vagrant up
```

To connect and use `fleetctl` which is CoreOS's service manager, we must add the ssh keys. This can be done with the command:

```
ssh-add `vagrant ssh-config | grep IdentityFile | awk '{print $2}' | head -n 1 | xargs echo`
```

The first instance (you can create a cluster of any size) will have the IP address `172.17.8.101`, so we can set the fleet tunnel with:

```
export FLEETCTL_TUNNEL=172.17.8.101:22
```

*Note: If you have used port 22 for another CoreOS cluster you may have to run `rm ~/.fleetctl/known_hosts` first to forget that IP address.*

You can test fleet is working with:

```
fleetctl list-machines
```

## Starting the Services

Start the global services with:

```
fleetctl start ../services/zglobal_hosts.service
fleetctl start ../services/zglobal_rabbitmq.service
```

This will start the `hosts` service and the RabbitMQ cluster on all nodes. You can check it is running by visiting the management console at `http://172.17.8.101:15673`.

Once RabbitMQ is running the `router` and two `hello_world` services can be started with:

```
fleetctl start ../services/router_v1.0.1@1
fleetctl start ../services/hello_world_v1.0.1@1
fleetctl start ../services/hello_world_v1.0.1@2
```

Now you should be able to curl the Vagrant Box with:

```
curl -X GET http://172.17.8.101:8080/v1/hello
```

This will:

1. Send an HTTP request for `/v1/hello` to the `router` service
2. The `router` will map that to an Alchemy request to the `hello_world` service
3. One of the running `hello_world` service instances will receive, process and respond to the request
4. The `router` will map the response back into HTTP and respond to the curl request.


