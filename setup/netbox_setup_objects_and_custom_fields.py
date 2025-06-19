#!/usr/bin/env python3

import os, sys, re
import argparse
import yaml
import json
import pynetbox

# adapted from sol1 implementation
from helpers.netbox_objects import NetboxCustomFields, NetboxCustomFieldChoiceSets, NetboxClusterTypes, NetboxClusters

from helpers.netbox_proxmox_api import NetBoxProxmoxAPIHelper


def get_arguments():
    # Initialize the parser
    parser = argparse.ArgumentParser(description="Import Netbox and Proxmox Configurations")

    # Add arguments for URL and Token
    parser.add_argument("--config", required=True, help="YAML file containing the configuration")

    # Parse the arguments
    args = parser.parse_args()

    # Return the parsed arguments
    return args


def __netbox_make_slug(in_str):
    return re.sub(r'\W+', '-', in_str).lower()


def create_custom_field_choice_sets_proxmox_vm_templates(proxmox_api_obj):
    proxmox_api_obj.proxmox_get_vm_templates()
    extra_choices = []

    for k, v in proxmox_api_obj.proxmox_vm_templates.items():
        extra_choices.append([str(k), v])

    ncfcs = NetboxCustomFieldChoiceSets(netbox_url, netbox_api_token, {'name': 'proxmox-vm-templates', 'extra_choices': extra_choices})
    return dict(ncfcs.obj)['id']


def create_custom_field_choice_sets_proxmox_vm_storage(proxmox_api_obj):
    proxmox_api_obj.proxmox_get_vm_storage_volumes()
    print(proxmox_api_obj.proxmox_storage_volumes)

    extra_choices = []

    for psv in proxmox_api_obj.proxmox_storage_volumes:
        extra_choices.append([psv, psv])

    ncfcs = NetboxCustomFieldChoiceSets(netbox_url, netbox_api_token, {'name': 'proxmox-vm-storage', 'extra_choices': extra_choices})
    return dict(ncfcs.obj)['id']


def create_custom_field_choice_sets_proxmox_lxc_templates(proxmox_api_obj):
    extra_choices = []

    for proxmox_node in proxmox_api_obj.proxmox_nodes:
        proxmox_api_obj.proxmox_get_lxc_templates(proxmox_node)

    proxmox_lxc_templates = proxmox_api_obj.proxmox_lxc_templates

    if proxmox_lxc_templates:
        for psv in proxmox_lxc_templates:
            extra_choices.append([psv, proxmox_lxc_templates[psv]])

        ncfcs = NetboxCustomFieldChoiceSets(netbox_url, netbox_api_token, {'name': 'proxmox-lxc-templates', 'extra_choices': extra_choices})
        return dict(ncfcs.obj)['id']
    
    return 0


def create_custom_field_choice_sets_proxmox_vm_cluster_nodes(proxmox_api_obj):
    extra_choices = []

    # get proxmox nodes
    #proxmox_api_obj.get_proxmox_nodes()
    proxmox_cluster_nodes = proxmox_api_obj.proxmox_nodes

    for pcn in proxmox_cluster_nodes:
        extra_choices.append([pcn, pcn])

    ncfcs = NetboxCustomFieldChoiceSets(netbox_url, netbox_api_token, {'name': 'proxmox-cluster-nodes', 'extra_choices': extra_choices})
    return dict(ncfcs.obj)['id']


def create_custom_field_choice_sets_proxmox_vm_type(proxmox_api_obj):
    extra_choices = []

    proxmox_vm_types = {
        'vm': 'Virtual Machine',
        'lxc': 'LXC Container'
    }

    for proxmox_vm_type in proxmox_vm_types:
        extra_choices.append([proxmox_vm_type, proxmox_vm_types[proxmox_vm_type]])

    ncfcs = NetboxCustomFieldChoiceSets(netbox_url, netbox_api_token, {'name': 'proxmox-vm-type', 'extra_choices': extra_choices})
    return dict(ncfcs.obj)['id']


def create_custom_field(netbox_url=None, netbox_api_token=None, name=None, label=None, choice_set_id=0, default=None):
    weight = 100
    description = ''

    if name in ['proxmox_lxc_templates']:
        group_name = 'Proxmox LXC'
    elif name in ['proxmox_node', 'proxmox_vmid', 'proxmox_vm_storage', 'proxmox_vm_type', 'proxmox_public_ssh_key']:
        group_name = 'Proxmox (common)'

        if name == 'proxmox_vm_type':
            weight = 200
        elif name == 'proxmox_vmid':
            weight = 300
        elif name == 'proxmox_vm_storage':
            weight = 400
        elif name == 'proxmox_public_ssh_key':
            weight = 500
    else:
        group_name = 'Proxmox VM'

    if name in ['proxmox_node', 'proxmox_vm_storage', 'proxmox_vm_templates', 'proxmox_lxc_templates', 'proxmox_vm_type']:
        object_types = ['virtualization.virtualmachine']
        input_type = {'value': 'select', 'label': 'Selection'}
    elif name in ['proxmox_disk_storage_volume']:
        object_types = ['virtualization.virtualdisk']
        input_type = {'value': 'select', 'label': 'Selection'}
    elif name in ['proxmox_public_ssh_key']:
        object_types = ['virtualization.virtualmachine']
        input_type = {'value': 'longtext', 'label': 'Text (long)'}
        description = 'For LXC (containers), you MUST add a SSH public key BEFORE you create the VM in NetBox'
    elif name in ['proxmox_vmid']:
        object_types = ['virtualization.virtualmachine']
        input_type = {'value': 'text', 'label': 'Text'}
    elif name in ['proxmox_is_lxc_container']:
        object_types = ['virtualization.virtualmachine']
        input_type = {'value': "boolean", 'label': 'Boolean (true/false)'}

    if input_type['value'] == 'select':
        nbcf = NetboxCustomFields(netbox_url, netbox_api_token,
                                {'weight': weight, 
                                 #'filter_logic': {'value': 'loose', 'label': 'Loose'},
                                 'filter_logic': 'disabled',
                                 'search_weight': 1000,
                                'object_types': object_types,
                                'type': input_type['value'],
                                'group_name': group_name,
                                'name': name,
                                'label': label,
                                'choice_set': choice_set_id,
                                'default': default})
    elif input_type['value'] == 'text':
        nbcf = NetboxCustomFields(netbox_url, netbox_api_token,
                                {'weight': weight,
                                 'filter_logic': 'disabled',
                                 'search_weight': 1000,
                                'object_types': object_types,
                                'type': input_type['value'],
                                'group_name': group_name,
                                'name': name,
                                'label': label})
    elif input_type['value'] == 'longtext':
        nbcf = NetboxCustomFields(netbox_url, netbox_api_token,
                                {'weight': weight,
                                 'filter_logic': 'disabled',
                                 'search_weight': 1000,
                                'object_types': object_types,
                                'type': input_type['value'],
                                'group_name': group_name,
                                'name': name,
                                'label': label,
                                'description': description})
    elif input_type['value'] == 'boolean':
        nbcf = NetboxCustomFields(netbox_url, netbox_api_token,
                                {'weight': weight,
                                 'filter_logic': 'disabled',
                                 'search_weight': 1000,
                                'object_types': object_types,
                                'type': input_type,
                                'group_name': group_name,
                                'name': name,
                                'label': label,
                                'required': True,
                                'default': False,
                                'label': label})
    
    return dict(nbcf.obj)['id']


if __name__ == "__main__":
    default_netbox_proxmox_name = 'Proxmox'
    default_netbox_cluster_role = default_netbox_proxmox_name
    default_netbox_cluster_name = 'proxmox-ve'
    default_netbox_vm_role = 'Proxmox VM'
    default_netbox_lxc_role = 'Proxmox LXC'

    args = get_arguments()

    app_config_file = args.config

    with open(app_config_file) as yaml_cfg:
        try:
            app_config = yaml.safe_load(yaml_cfg)
        except yaml.YAMLError as exc:
            raise ValueError(exc)
        except IOError as ioe:
            raise ValueError(ioe)

    netbox_url = f"{app_config['netbox_api_config']['api_proto']}://{app_config['netbox_api_config']['api_host']}:{app_config['netbox_api_config']['api_port']}/"
    netbox_api_token = f"{app_config['netbox_api_config']['api_token']}"

    # init NetBox Proxmox API integration
    p = NetBoxProxmoxAPIHelper(app_config)

    # setup defaults and override from config values later
    proxmox_cluster_name = default_netbox_cluster_name
    vm_cluster_role = default_netbox_cluster_role
    vm_role = default_netbox_vm_role
    lxc_role = default_netbox_lxc_role

    if 'proxmox' in app_config:
        if 'cluster_name' in app_config['proxmox']:
            proxmox_cluster_name = app_config['proxmox']['cluster_name']

    if 'netbox' in app_config:
        if 'cluster_role' in app_config['netbox']:
            vm_cluster_role = app_config['netbox']['cluster_role']

        if 'vm_role' in app_config['netbox']:
            vm_role = app_config['netbox']['vm_role']

        if 'lxc_role' in app_config['netbox']:
            lxc_role = app_config['netbox']['lxc_role']

    # vm clusters and types
    nbct = NetboxClusterTypes(netbox_url, netbox_api_token, {'name': vm_cluster_role, 'slug': __netbox_make_slug(vm_cluster_role)})
    netbox_cluster_type_id = dict(nbct.obj)['id']

    nbc = NetboxClusters(netbox_url, netbox_api_token, {'name': proxmox_cluster_name, 'type': netbox_cluster_type_id, 'status': 'active'})
    netbox_cluster_id = dict(nbc.obj)['id']

    # custom field choice sets
    netbox_field_choice_sets_templates_id = create_custom_field_choice_sets_proxmox_vm_templates(p)

    netbox_field_choice_sets_vm_storage_volumes_id = create_custom_field_choice_sets_proxmox_vm_storage(p)

    netbox_field_choice_sets_lxc_templates_id = create_custom_field_choice_sets_proxmox_lxc_templates(p)

    netbox_field_choice_sets_proxmox_nodes_id = create_custom_field_choice_sets_proxmox_vm_cluster_nodes(p)

    netbox_field_choice_sets_proxmox_vm_types_id = create_custom_field_choice_sets_proxmox_vm_type(p)

    # custom fields

    # VM template id
    custom_field_template_id = create_custom_field(netbox_url, netbox_api_token, 'proxmox_vm_templates', 'Proxmox VM Templates', netbox_field_choice_sets_templates_id, str(min(p.proxmox_vm_templates.keys())))

    # VM proxmox node id
    custom_field_proxmox_node_id = create_custom_field(netbox_url, netbox_api_token, 'proxmox_node', 'Proxmox node', netbox_field_choice_sets_proxmox_nodes_id, p.proxmox_nodes[0])

    # proxmox_vmid
    custom_field_proxmox_vm_id = create_custom_field(netbox_url, netbox_api_token, 'proxmox_vmid', 'Proxmox Virtual machine ID (vmid)')

    # proxmox_public_ssh_key
    custom_field_proxmox_public_ssh_key_id = create_custom_field(netbox_url, netbox_api_token, 'proxmox_public_ssh_key', 'Proxmox public SSH key')

    # proxmox_disk_storage_volume
    custom_field_proxmox_disk_storage_volume_id = create_custom_field(netbox_url, netbox_api_token, 'proxmox_disk_storage_volume', 'Proxmox Disk Storage Volume', netbox_field_choice_sets_vm_storage_volumes_id, p.proxmox_storage_volumes[0])

    # proxmox_vm_storage
    custom_field_proxmox_disk_storage_volume_id = create_custom_field(netbox_url, netbox_api_token, 'proxmox_vm_storage', 'Proxmox VM Storage', netbox_field_choice_sets_vm_storage_volumes_id, p.proxmox_storage_volumes[0])

    # proxmox_vm_type
    custom_field_proxmox_vm_type = create_custom_field(netbox_url, netbox_api_token, 'proxmox_vm_type', 'Proxmox VM Type', netbox_field_choice_sets_proxmox_vm_types_id, 'vm')

    # proxmox_lxc_templates
    if netbox_field_choice_sets_lxc_templates_id > 0:
        #custom_field_proxmox_disk_storage_volume_id = create_custom_field(netbox_url, netbox_api_token, 'proxmox_lxc_templates', 'Proxmox LXC Templates', netbox_field_choice_sets_lxc_templates_id, str(min(p.proxmox_lxc_templates.keys())))
        if len(p.proxmox_lxc_templates.keys()):
            custom_field_proxmox_disk_storage_volume_id = create_custom_field(netbox_url, netbox_api_token, 'proxmox_lxc_templates', 'Proxmox LXC Templates', netbox_field_choice_sets_lxc_templates_id, str(min(p.proxmox_lxc_templates.keys())))
        else:
            custom_field_proxmox_disk_storage_volume_id = create_custom_field(netbox_url, netbox_api_token, 'proxmox_lxc_templates', 'Proxmox LXC Templates', netbox_field_choice_sets_lxc_templates_id, "")
