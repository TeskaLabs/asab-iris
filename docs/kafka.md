# ASAB Iris and Apache Kafka

ASAB Iris can receive messages from Apache Kafka that will trigger email or instant message.

## Apache Kafka configuration

In the ASAB Iris configuration, specify following section:

```
[kafka]
topic=your_topic
group_id=your_group_id
bootstrap_servers=kafka-1,kafka-2,kafka-3
```

## E-mail format

```
{
    "type": "email",
    "to": ["john.doe@example.com", "jane.doe@example.com"],
    "body": {
    	"template": "hello.md"
    }
}
```
