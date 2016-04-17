# Alchemy Micro-services Framework
<img src="./assets/c60.jpg" align="right" alt="Buckminsterfullerene" />

[![Build Status](https://travis-ci.org/LoyaltyNZ/alchemy-framework.svg?branch=master)](https://travis-ci.org/LoyaltyNZ/alchemy-framework) [![License](https://img.shields.io/badge/license-LGPL--3.0-blue.svg)](http://www.gnu.org/licenses/lgpl-3.0.en.html)

**Alchemy** is a framework for creating highly available systems that are built from [micro-services](http://martinfowler.com/articles/microservices.html). Alchemy includes service discovery, easy deployment, smart load balancing and is a polyglot, so you can use the best languages to solve all your problems. Alchemy already has implementations in [Node.js](https://github.com/LoyaltyNZ/alchemy-ether) and [Ruby](https://github.com/LoyaltyNZ/alchemy-flux).

This repository is a description of how Alchemy works, how it is implemented and how to create services. Examples are included of how to write services and use Alchemy with:

1. [Docker and `docker-compose`](./docker) which can be used with [Travis CI](https://travis-ci.org/) (results are [here](https://travis-ci.org/LoyaltyNZ/alchemy-framework))
2. [Vagrant with CoreOS](./vagrant) for local testing
3. An [Amazon Web Services Cloud Formation template](./cloud_formation) using an Elastic Load Balancer, Auto Scaling Groups and CoreOS for production and other cloud environments

## How Alchemy Services Work

Alchemy uses the [RabbitMQ](https://www.rabbitmq.com/) message broker to pass requests between services. Each Alchemy service registers two queues with RabbitMQ:

1. a **service queue** is the name of the service and is shared amongst all instances of a service
2. a **response queue** is the name of a service instance so is unique

A service communicates by putting a request (that includes its own **response queue**) on a target's **service queue**. Then an instance of the target service will consume, process, then respond to the request on the received **response queue**.

** *For the purpose of clarity I will note a service with letters e.g. `A`, `B` and service instances with numbers, e.g. `A1` is service `A` instance `1`.* **

For example, service `A1` wants to message service `B`:

```
|----------|                                                  |------------|
| RabbitMQ | <-- 1. Send request on queue B   --------------- | Service A1 |
|          |                                                  |            |
|          | --- 2. Consume request from B  -> |------------| |            |
|          |                                   | Service B1 | |            |
|          | <-- 3. Respond on queue A1     -- |------------| |            |
|          |                                                  |            |
|----------| --- 4. Receive response on A1  ----------------> |------------|
```

Service `A` sends a request to the **service queue** `B`. This message is consumed by a service instance `B1`, processed, and the result published on the **response queue** of the service instance `A1` where it can be received.

This design makes the Alchemy framework:

* **High Availability**: because RabbitMQ can run as a [cluster](https://www.rabbitmq.com/clustering.html) across multiple machines where queues can be [highly available](https://www.rabbitmq.com/ha.html) and multiple instances of Alchemy services can be run simultaneously. **No single machine is a point of failure in the Alchemy Framework.
* **Smart Load Balancing**: If several instances of the service `B` were running with different available resources, each instance would regulate its own load by only consuming messages it can process. Compared to round-robin load balancing where instances with the least resources would be under heavy load while instances with the most resources are idle.
* **Service Discovery**: service `A1` does not know that it is communicating with service instance `B1` so cannot know where it is deployed. It only knows that the service `B` is who it is calling. This abstraction means that `B1` could be on a different computer, a different data center, or in a different hemisphere.
* **Easy Deployment**: starting and stopping an instance of a service can be done without notifying any other part of the system. So, no [Consul](https://www.consul.io/) or other service registry is needed. Additionally, if a new version of a service became available, it can be deployed alongside the old version to have a zero downtime upgrade.
* **Error Recovery**: If `B1` dies while processing a message RabbitMQ will put the message back on the queue which can then be processed by another instance. Service `A1` will not know this has happened and will probably just see the message take longer than usual. This also means that messages may be processed more than once, so implementing **idempotent** micro-services is recommended.
* **Polyglot Architecture**: Service `A1` could be implemented in Ruby while `B1` is implemented in Node.js. They both just have to follow the same standard as described in this documentation. Even service instances can be implemented in different languages (if you wanted to compare performance).

### Resources and Routing

An individual service will likely implement many related **resources**, e.g. an `authentication` service could implement `session`, `user`, and `credential` resources. In Alchemy it is possible for service to communicate directly with a resource without even knowing which service implements it. This disconnects the implementation of a resource from a service, so Alchemy services only need to know what they want and not where to find it.

In Alchemy each resource is represented by a **path**, e.g. `/v1/users`. The service binds its service queue to the `resources.exchange` [RabbitMQ Topic Exchange](https://www.rabbitmq.com/tutorials/tutorial-five-ruby.html) with a  **binding key** created from the path, e.g. `v1.users.#`. For a service to call a resource it posts a message to the `resources.exchange` with a **routing key** created from the path it wants to call, e.g. `/v1/users/1337` is converted to `v1.users.1337`, where RabbitMQ will route the message to the correct service queue.

For example, service `A1` wants to send a message with path `/v1/users/1337`:

```
|----------|                                                  |------------|
| RabbitMQ | <-- 1. Send request to /v1/users/1337 ---------- | Service A1 |
| resource |                                                  |            |
| exchange | --- 2. Consume request from B  -> |------------| |            |
|          |                                   | Service B1 | |            |
|          | <-- 3. Respond on queue A1     -- |------------| |            |
|          |                                                  |            |
|----------| --- 4. Receive response on A1  ----------------> |------------|
```

Service `B1` implements the resource with path `/v1/users`, when it starts it binds its **service queue** `B` to the exchange `resources.exchange` with the binding key `v1.users.#`. When a message with a path `/v1/users/1337` is sent, the path is converted into the **routing key** `v1.users.1337` and sent on the `resources.exchange` which routes the message to the service queue `B` for `B1` to process and respond.

This method of resource routing will route all sub-paths to a bound resource path. This means that it is important to ensure there are no routing conflicts exist between resources.

## The Alchemy API

The specific API for each Alchemy implementation may be slightly different because of the implementation language, but they follow similar designs and function signatures.

### Service Construction

A service is initialized with `initialize(name, options = {}, service_fn)` where the `name` will be the name of the **service queue** and used to generate a **response queue** by adding a random string after the name. The keys for options are:

1. `amqp_uri`: the URL location of RabbitMQ e.g. `"amqp://localhost"`
2. `prefetch`: the number of messages to prefetch and process in parallel
3. `timeout`: the length of time in milliseconds that the service will wait for a response to a message
4. `resource_paths` and array of paths as strings, e.g. `["/v1/posts","/v1/tags"]`

The `service_fn` is the function that will process the received messages (that are defined below). It can return an object with keys:

1. *body*: A string of body information
2. *headers*: an object with headers in is, e.g. {"X-HEADER-KEY": "value"}
3. *status_code*: an HTTP status code

For example:

```
{
  "body": "{\"created_at\":\"2016-02-27T04:31:58.200Z\"}",
  "http_status": "200",
  "headers": {
    "Content-Type": "application/json; charset=UTF-8"
  }
}
```

#### When Processing a Message Goes Bad

Sometimes when processing a message an error occurs that requires the process to be tried again. The `service_fn` can **not acknowledg** (or **NAck**) processing the message by throwing or returning a `NAckError`. This error will cause RabbitMQ to put the message back on the queue to be retried again by the original or another service.

**This is very dangerous!** If the cause of the NAckError happens repeatedly the message will be retried (potentially indefinitely) and cause your system to run out of resources. It is best used in cases where the cause of the error would quickly be resolved.

### Life Cycle

The life cycle functions are:

1. `start` to create the queues in RabbitMQ, bind the resources to the exchange, and start listening to the service queue for messages to process.
2. `stop` will shutdown the service by first stopping processing new messages from the service queue, then waiting for the currently processing messages and requests to finish, then shutting down the RabbitMQ connection.

### Communication

The format of an Alchemy request on a queue reuses concepts from the HTTP protocol like status codes, headers, to be more interoperable and easier to understand. A request sent across RabbitMQ is encoded as a JSON string with the keys:

Request Information:

1. *body*: A string of the body, e.g '<html>hello</html>'
2. *verb*: The HTTP verb for the request, e.g. `GET`
3. *headers*: an object with headers in is, e.g. `{"X-HEADER-KEY": "value"}`
4. *path*: the path of the request, e.g. `"/v1/users/1337"`
5. *query*: an object with keys for query, e.g. `{'q': 'alchemy'}`

Call information:

1. *scheme*: the scheme used for the call, e.g. `http`
2. *host*: the host called to make the call, e.g. `localhost`
3. *port*: the port the call was made on, e.g. `8080`

Authentication information:

1. *session*: this is an object of undefined structure that can be passed in the message so that a service does not need to re-authenticate with each message (this can be quite expensive in a call hitting many services).

For example a call to create a user will be:

```
{
  "body": "{\"name\":\"alice\",\"password\":\"1234\"}",
  "verb": "POST",
  "headers": {
    "Content-Type": "application/json; charset=UTF-8"
  },
  "path": "/users",
  "query": {},
  "scheme": "https",
  "host": "localhost",
  "port": 8080,
  "session": {'user_id': "2", 'session_id': "4321"}
}
```

Alchemy allows a service to send a `request`, which requires a response, and to send a `message`, which does not require a response.

Sending requests to another service can either be done directly to a `service` by providing the name of the service queue, or to a `resource` via the resource exchange that will use the `path` contained within the request to create the routing key.

This leads to four options driven through four functions:

1. `send_message_to_service(service_name, message)`: send a message to a service and not require a response
2. `send_message_to_resource(message)`: send a message to a resource and not require a response
3. `send_request_to_service(service_name, message)`: send a request to a service and require a response
4. `send_request_to_resource(message)`: send a request to a resource and require a response

#### When Sending a Request or Message Goes Bad

When a message is sent to either a service that does not exist or to a resource path that is not bound to a service, the function will return or throw a `MessageNotDeliveredError`. This is essentially a [`404` no found error](https://en.wikipedia.org/wiki/List_of_HTTP_status_codes#404) as the message never reached a service to be processed, but it allows a service to deal with that in its own way (like a fail whale).

When a request is sent it will not wait forever for a response. If the request takes longer than the option `timeout` a `TimeoutError` is thrown or returned. This is essentially a [`408` request timeout error](https://en.wikipedia.org/wiki/List_of_HTTP_status_codes#408) which can be handled by the service. A timeout could happen if there is a service queue, but no service listening on the queue.

#### AMQ Message Options

The AMQ/RabbitMQ message options that are being used by Alchemy to send requests are:

1. `message_id`: a unique identifier for the request
2. `type`: `http`
3. `content_encoding`: `'8bit'`
4. `content_type`: `'application/json'`, this is the type of the request on RabbitMQ not the type of the actual message sent by the service.
5. `expiration`: the options `timeout` value
6. `reply_to`: the name of the response queue that the response message should be put on. If no `reply_to` is set, then no response is sent (this is how messages are sent)
7. `mandatory`: `true` this will make messages be returned if they do not find a queue

The options for the response are:

1. `message_id`: a unique identifier for the response
2. `type`: `http_response`
3. `correlation_id`: The `message_id` of the request to be responded to

## Router

An important part of Alchemy is the gateway between a client calling over HTTP and the services which are listening on RabbitMQ. The [Alchemy Router](https://github.com/LoyaltyNZ/alchemy-router) is this gateway that converts incoming HTTP requests into Alchemy requests sent on over RabbitMQ.

The Router can be used either:

1. as an application installed using npm via `npm install -g alchemy-router` then run with `alchemy-router`
2. as an [npm package](https://www.npmjs.com/package/alchemy-router) that can be extended and customised by writing [express](https://github.com/expressjs/express) middelware.
3. as a Docker container `quay.io/loyalty_nz/alchemy-router`

The Router works as follows:

1. An HTTP request is sent from a client to Alchemy
2. The HTTP request is received by the Router and converted into an Alchemy request
3. The request is sent to the correct Alchemy service or resource
4. The response is unpacked and returned to the HTTP client

In a typical Alchemy deployment there would be many instances of the Router, load balanced by an application like [Elastic Load Balancer](https://aws.amazon.com/elasticloadbalancing/) or [HAProxy](http://www.haproxy.org/). This can add performance and availability benefits.

## Example Sinatra API Micro-Service Application

The Ruby implementation of Alchemy, [Alchemy Flux](https://rubygems.org/gems/alchemy-flux), comes with a [Rack](https://github.com/rack/rack) server implementation that handles the life-cycle and processing requests of an Alchemy service. The Alchemy Rack server supports frameworks like [Rails](http://rubyonrails.org/), [Sinatra](http://www.sinatrarb.com/) and [Hoodoo](http://hoodoo.cloud/) to make it very easy to build new, or move old, services onto Alchemy.

For example, a simple Sinatra application in the Alchemy framework has the files:

```
# ./Gemfile
source 'https://rubygems.org'

gem 'sinatra'
gem 'alchemy-flux'
```

```
# ./config.ru
ENV['ALCHEMY_SERVICE_NAME'] = 'helloworld.service'
ENV['ALCHEMY_RESOURCE_PATHS'] = '/v1/hello'

require 'alchemy-flux'
require './service'
run Sinatra::Application
```

```
# ./service.rb
require 'sinatra'

get '/v1/hello' do
  content_type :json
  {'hello' => 'world!'}.to_json
end
```

To run this service we use `rackup` and specify `alchemy` as the Rack server:

```
bundle install
bundle exec rackup -s alchemy
```

The service will now be listening on RabbitMQ for incoming messages, running a router (as described above) and calling the router with `/v1/hello` over HTTP this will route the message to the Sinatra micro-service.

## Alchemy Implementations (So Far)

Alchemy Framework Implementations:

1. **Ruby** has [Alchemy-Flux](https://rubygems.org/gems/alchemy-flux) which is the reference implementation
2. **Node.js** has [Alchemy Ether](https://www.npmjs.com/package/alchemy-ether)

## Projects that use Alchemy

1. [Hoodoo](http://hoodoo.cloud/) A micro-services CRUD and RESTful framework
2. [Alchemy Resource](https://github.com/LoyaltyNZ/alchemy-resource) a Hoodoo interoperable ramework for Node.js
3. [Router](https://github.com/LoyaltyNZ/alchemy-router) a router/gateway from HTTP calls to Alchemy services
