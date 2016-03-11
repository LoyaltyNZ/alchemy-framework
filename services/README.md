# Example Services

CoreOS Fleet Service Definitions:

* Hosts Service - Writes entries into `/etc/hosts` based on members of the etcd cluster
* RabbitMQ [Docker Image](https://hub.docker.com/_/rabbitmq/) - Service Definition for running a RabbitMQ Cluster on CoreOS
* Router [Github](https://github.com/LoyaltyNZ/alchemy-router) [Docker Image](https://quay.io/loyalty_nz/alchemy-router) - Accepts HTTP requests from the ELB, and places requests onto RabbitMQ.
* Hello World [Github](https://github.com/LoyaltyNZ/alchemy-hello-world) [Docker Image](https://quay.io/loyalty_nz/alchemy-hello-world) - Example Micro Service.
