#!/bin/bash

# Script to create OpenStack resources based on the documentation
# This script creates projects and networks/subnets as specified

set -e  # Exit on any error

# Configuration variables
PROJECT_NAME="MDC-OPCP-VCF"
CS_NETWORK_NAME="CLOUDSTORE"
VCF_MGT_NETWORK_NAME="VCF-MGT"
VCF_OVERLAY_MD_NETWORK_NAME="VCF-Overlay-MD"
VCF_VMOTION_MD_NETWORK_NAME="VCF-Vmotion-MD"
VCF_VSAN_MD_NETWORK_NAME="VCF-Vsan-MD"
VCF_OVERLAY_WKLD_NETWORK_NAME="VCF-Overlay-WKLD"
VCF_VMOTION_WKLD_NETWORK_NAME="VCF-Vmotion-WKLD"
VCF_VSAN_WKLD_NETWORK_NAME="VCF-Vsan-WKLD"
EXTNET_NETWORK_NAME="Extnet"

# Create VCF project
echo "Creating VCF project..."
openstack project create --domain keycloak "$PROJECT_NAME"

# VCF-MGT Network and Subnet
echo "Creating VCF-MGT network and subnet..."
openstack network create --project "$PROJECT_NAME" --provider-network-type vlan --provider-physical-network physnet1 --provider-segment 801 "$VCF_MGT_NETWORK_NAME"
openstack subnet create --network "$VCF_MGT_NETWORK_NAME" --subnet-range 172.18.2.0/22 --allocation-pool start=172.18.3.2,end=172.18.3.254 --gateway 172.18.3.1 "$VCF_MGT_NETWORK_NAME"-subnet

# CLOUDSTORE Network and Subnet
echo "Creating CLOUDSTORE network and subnet..."
openstack network create --share --provider-network-type vlan --provider-physical-network physnet1 --provider-segment 800 "$CS_NETWORK_NAME"
openstack subnet create --network "$CS_NETWORK_NAME" --subnet-range 172.18.1.0/24 --allocation-pool start=172.18.1.15,end=172.18.1.253 --gateway 172.18.1.254 "$CS_NETWORK_NAME"-subnet

# Other Networks (without DHCP)
echo "Creating other networks without DHCP..."

# VCF-Overlay-MD
openstack network create --project "$PROJECT_NAME" --provider-network-type vlan --provider-physical-network physnet1 --provider-segment 802 "$VCF_OVERLAY_MD_NETWORK_NAME"
openstack subnet create --network "$VCF_OVERLAY_MD_NETWORK_NAME" --subnet-range 172.18.4.0/24 --no-dhcp --gateway 172.18.4.1 "$VCF_OVERLAY_MD_NETWORK_NAME"-subnet

# VCF-Vmotion-MD
openstack network create --project "$PROJECT_NAME" --provider-network-type vlan --provider-physical-network physnet1 --provider-segment 803 "$VCF_VMOTION_MD_NETWORK_NAME"
openstack subnet create --network "$VCF_VMOTION_MD_NETWORK_NAME" --subnet-range 172.18.5.0/24 --no-dhcp --gateway 172.18.5.1 "$VCF_VMOTION_MD_NETWORK_NAME"-subnet

# VCF-Vsan-MD
openstack network create --project "$PROJECT_NAME" --provider-network-type vlan --provider-physical-network physnet1 --provider-segment 804 "$VCF_VSAN_MD_NETWORK_NAME"
openstack subnet create --network "$VCF_VSAN_MD_NETWORK_NAME" --subnet-range 172.18.6.0/24 --no-dhcp --gateway 172.18.6.1 "$VCF_VSAN_MD_NETWORK_NAME"-subnet

# VCF-Overlay-WKLD
openstack network create --project "$PROJECT_NAME" --provider-network-type vlan --provider-physical-network physnet1 --provider-segment 805 "$VCF_OVERLAY_WKLD_NETWORK_NAME"
openstack subnet create --network "$VCF_OVERLAY_WKLD_NETWORK_NAME" --subnet-range 172.18.7.0/24 --no-dhcp --gateway 172.18.7.1 "$VCF_OVERLAY_WKLD_NETWORK_NAME"-subnet

# VCF-Vmotion-WKLD
openstack network create --project "$PROJECT_NAME" --provider-network-type vlan --provider-physical-network physnet1 --provider-segment 806 "$VCF_VMOTION_WKLD_NETWORK_NAME"
openstack subnet create --network "$VCF_VMOTION_WKLD_NETWORK_NAME" --subnet-range 172.18.8.0/24 --no-dhcp --gateway 172.18.8.1 "$VCF_VMOTION_WKLD_NETWORK_NAME"-subnet

# VCF-Vsan-WKLD
openstack network create --project "$PROJECT_NAME" --provider-network-type vlan --provider-physical-network physnet1 --provider-segment 807 "$VCF_VSAN_WKLD_NETWORK_NAME"
openstack subnet create --network "$VCF_VSAN_WKLD_NETWORK_NAME" --subnet-range 172.18.9.0/24 --no-dhcp --gateway 172.18.9.1 "$VCF_VSAN_WKLD_NETWORK_NAME"-subnet

# Extnet
openstack network create --project "$PROJECT_NAME" --provider-network-type vlan --provider-physical-network physnet1 --provider-segment 808 "$EXTNET_NETWORK_NAME"
openstack subnet create --network "$EXTNET_NETWORK_NAME" --subnet-range 172.18.10.0/24 --no-dhcp --gateway 172.18.10.1 "$EXTNET_NETWORK_NAME"-subnet

echo "All OpenStack resources have been created successfully!"
