#!/bin/bash
rm -rf join-order-benchmark
git clone https://github.com/seokjeongeum/join-order-benchmark.git
cd join-order-benchmark || exit
mv -f ./csv_files/schematext.sql ./csv_files/schematext_backup.sql
apt install -y wget
wget http://homepages.cwi.nl/~boncz/job/imdb.tgz
sudo tar -zxvf imdb.tgz -C csv_files
mv -f ./csv_files/schematext_backup.sql ./csv_files/schematext.sql
mysql -u root -ppassword < csv_files/schematext.sql
mysql -u root -ppassword imdbload < csv_files/fkindexes.sql
./load_data_mysql.sh
cd ~/OpAdviserPrivate
