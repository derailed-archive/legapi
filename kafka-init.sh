are_brokers_available() {
    expected_num_brokers=3 # replace this with a proper value
    num_brokers=$(("$(zookeeper-shell.sh zookeeper:2181 ls /brokers/ids 2>/dev/null | grep -o , | wc -l)" + 1))
    return ((num_brokers >= expected_num_brokers))
}

while ! are_brokers_available; do
    sleep 1
done

echo "Starting Custom Initiation"

/opt/bitnami/kafka/bin/kafka-topics.sh --zookeeper zookeeper:2181 --create  --replication-factor 1 --partitions 2 --topic guild
/opt/bitnami/kafka/bin/kafka-topics.sh --zookeeper zookeeper:2181 --list

echo "Initialization Completed"