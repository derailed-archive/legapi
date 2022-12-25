#!/bin/bash
echo "sleeping for 2 seconds"
sleep 2

echo mongo_setup.sh time now: `date +"%T" `
mongosh --host mongo:27017 <<EOF
  rs.initiate();
EOF