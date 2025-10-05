#!/bin/bash
set -e

HADOOP_VERSION=3.3.6

APACHE_VAULT='http://localhost:8080/archive.apache.org'
wget -O/dev/null --debug --max-redirect=0 "$APACHE_VAULT/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz"
