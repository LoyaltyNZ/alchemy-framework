# Using Docker Compose to Build your Alchemy Platform

Docker compose is a tool for defining and running multi-container Docker applications. In this example we will start two instances of the `hello_world` service, and one instance of the `router` service.

This repository also uses Docker compose to run an automated test suite in [Travis CI](https://travis-ci.org/), the definition can be seen in the [travis.yml](../travis.yml) and the results at [travis-ci.org](https://travis-ci.org/LoyaltyNZ/alchemy-framework).

## Getting Docker running on OSX

Install the tools:

1. `brew install docker-machine`
1. `brew install docker`
1. `brew install docker-compose`

Start Docker Machine VM:

1. `docker-machine start`
1. `eval $(docker-machine env)`

## Docker Compose

To start the Alchemy framework with Docker Compose:

1. `docker-compose up`

The docker compose file will start:

1. A RabbitMQ docker container with the management dashboard available at http://<DOCKER_IP>:15674 with username and password as "guest"
2. The Alchemy Router to receive HTTP messages on port 8080 and send them to the relevant services
3. 2 instances of the `hello_world` service, which can process `/v1/hello` requests

To test the services `curl "http://<DOCKER_IP>:8080/v1/hello" `, with docker machine that will be `curl "http://$(docker-machine ip):8080/v1/hello"`

This will:

1. Send an HTTP request for `/v1/hello` to the `router` service
2. The `router` will map that to an Alchemy request to the `hello_world` service
3. One of the running `hello_world` service instances will receive, process and respond to the request
4. The `router` will map the response back into HTTP and respond to the curl request.

