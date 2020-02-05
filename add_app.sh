#!/bin/bash
TOKEN=$(consul kv get tokens/admin/by_username/admin|cut -d \" -f 8)
read -p "Enter instance name: " instance
read -p "Enter instance role: " role
curl -k -X POST -H "Content-type: application/json" -H "Authorization: Token $TOKEN" --data '{"server_name" : "'"$instance"'", "role" : "'"$role"'"}' 'https://127.0.0.1/api/panels/new_panel'

