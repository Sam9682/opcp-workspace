#!/bin/bash

# Script to list all OpenStack networks including VLAN IDs

# Check if openstack command is available
if ! command -v openstack &> /dev/null; then
    echo "Error: openstack command could not be found"
    exit 1
fi

# Function to get project ID by project name
get_project_id() {
    local project_name="$1"
    openstack project show "$project_name" -f value -c id 2>/dev/null || echo ""
}

# Function to list projects and let user select one
select_project() {
    echo "Available Projects:"
    echo "=================="
    
    # List all projects
    projects=$(openstack project list -f value -c Name)
    
    if [ -z "$projects" ]; then
        echo "No projects found"
        return 1
    fi
    
    # Display projects with numbers
    echo "$projects" | nl -nln | sed 's/^ *//'
    
    echo ""
    read -p "Select a project by number (or press Enter to list all networks): " choice
    
    if [ -z "$choice" ]; then
        return 0  # No project selected, list all networks
    fi
    
    # Validate choice
    project_count=$(echo "$projects" | wc -l)
    if [ "$choice" -lt 1 ] || [ "$choice" -gt "$project_count" ]; then
        echo "Invalid selection"
        return 1
    fi
    
    # Get the project name based on selection
    project_name=$(echo "$projects" | sed -n "${choice}p")
    
    # Get the project ID
    project_id=$(get_project_id "$project_name")
    
    if [ -z "$project_id" ]; then
        echo "Error: Could not retrieve project ID for '$project_name'"
        return 1
    fi
    
    echo "Selected Project: $project_name (ID: $project_id)"
    echo ""
    
    # Set the project ID for filtering
    PROJECT_ID="$project_id"
    return 0
}

echo "OpenStack Networks with VLAN IDs:"
echo "=================================="

# Try to select a project
if select_project; then
    # If project was selected, filter networks by project
    if [ -n "$PROJECT_ID" ]; then
        echo "Listing networks for project: $PROJECT_ID"
        echo ""
        echo "Network Name | Network ID | Network Type | VLAN ID"
        echo "---------------------------------------------------"
        openstack network list --project "$PROJECT_ID" --format table -c Name -c ID -c ProviderNetworkType -c ProviderSegmentationId
        
        echo ""
        echo "Detailed view with additional information:"
        echo "========================================="
        
        # Get detailed information for each network in the selected project
        for network in $(openstack network list --project "$PROJECT_ID" -f value -c ID); do
            echo "Network ID: $network"
            name=$(openstack network show "$network" -f value -c name)
            network_type=$(openstack network show "$network" -f value -c provider:network_type)
            vlan_id=$(openstack network show "$network" -f value -c provider:segmentation_id)
            subnets=$(openstack network show "$network" -f value -c subnets)
            
            echo "  Name: $name"
            echo "  Type: $network_type"
            echo "  VLAN ID: ${vlan_id:-N/A}"
            if [ -n "$subnets" ]; then
                echo "  Subnet UUID(s):"
                for subnet in $(echo "$subnets" | tr -d "[],'\"" ); do
                    echo "    - $subnet"
                done
            else
                echo "  Subnet UUID(s): N/A"
            fi
            echo "---"
        done
    else
        # No project selected, list all networks
        echo "Network Name | Network ID | Network Type | VLAN ID"
        echo "---------------------------------------------------"
        openstack network list --format table -c Name -c ID -c ProviderNetworkType -c ProviderSegmentationId 
        
        echo ""
        echo "Detailed view with additional information:"
        echo "========================================="
        
        # Get detailed information for each network
        for network in $(openstack network list -f value -c ID); do
            echo "Network ID: $network"
            name=$(openstack network show "$network" -f value -c name)
            network_type=$(openstack network show "$network" -f value -c provider:network_type)
            vlan_id=$(openstack network show "$network" -f value -c provider:segmentation_id)
            
            echo "  Name: $name"
            echo "  Type: $network_type"
            echo "  VLAN ID: ${vlan_id:-N/A}"
            echo "---"
        done
    fi
else
    echo "Failed to select a project. Listing all networks instead."
    echo ""
    echo "Network Name | Network ID | Network Type | VLAN ID"
    echo "---------------------------------------------------"
    openstack network list --format table -c Name -c ID -c ProviderNetworkType -c ProviderSegmentationId 
    
    echo ""
    echo "Detailed view with additional information:"
    echo "========================================="
    
    # Get detailed information for each network
    for network in $(openstack network list -f value -c ID); do
        echo "Network ID: $network"
        name=$(openstack network show "$network" -f value -c name)
        network_type=$(openstack network show "$network" -f value -c provider:network_type)
        vlan_id=$(openstack network show "$network" -f value -c provider:segmentation_id)
        
        echo "  Name: $name"
        echo "  Type: $network_type"
        echo "  VLAN ID: ${vlan_id:-N/A}"
        echo "---"
    done
fi

