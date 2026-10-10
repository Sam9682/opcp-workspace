// VCF domain JSON generation.
//
// The VCF checklist tab collects customer answers keyed by `vcfConfig` row ids
// (e.g. `vcf-mgmt-network-name`). The CloudStore VCF deployment consumes two
// flat JSON files instead: one for the management domain and one for the
// workload domain. Each file has a fixed set of keys with sensible defaults;
// where a key corresponds to a customer-input row, the customer's answer (when
// provided and non-empty) overrides the default.
//
// `*_TEMPLATE` holds the default value set for a domain. `*_KEY_TO_ROW_ID` maps
// the JSON keys that are backed by a `vcfConfig` row to that row id; keys not
// present in the map (debug, openstack_*, pairing_source, ...) always keep
// their template default. `buildDomainJson` overlays the answers onto the
// template and preserves the original JSON value type (boolean stays boolean).

type JsonValue = string | number | boolean;

export const MANAGEMENT_DOMAIN_TEMPLATE: Record<string, JsonValue> = {
  appliance_password: 'ChangeMe',
  appliance_xapikey: 'ChangeMe',
  bootstrap_dns_server: '192.168.220.47',
  customer_network_dhcp_ip: '192.168.220.2',
  customer_network_name: 'customerapi-network',
  debug: true,
  dns_create_records: true,
  dns_server: '10.105.40.3',
  dns_zone: 'internal.cloudstore.ovh',
  esxi_install_timeout: '2100',
  esxi_root_password: 'ChangeMe',
  esxi_setup_script: 'true',
  external_network_id: 'dbe8c824-9b43-47df-a6df-0bfc19fdecf7',
  flavor_name: 'vcf_no_sb',
  image_name: 'esxi-9.0.2-user-data',
  keycloak_clusterissuer: 'customer-issuer',
  keycloak_request_cpu: '500m',
  keycloak_request_memory: '1024Mi',
  lacp: false,
  ntp_server: '10.105.40.3',
  openstack_auth_type: 'v3applicationcredential',
  openstack_endpoint_type: 'internal',
  openstack_identity_api_version: '3',
  overlay_network_id: '966eb2ae-ad79-4d86-baf9-45164a511c2c',
  overlay_subnet_id: 'ee7ffa41-a3cc-48b8-887f-ea7bf4f3b5d8',
  overlay_subnet_range: '10.105.46.0/24',
  overlay_vlan_id: '2046',
  pairing_source: 'pci',
  vcf_deployer_ip: '192.168.220.8',
  vcf_deployer_url:
    'http://vcf-ova.vcf-ova.svc.cluster.local/vcf_deployer-all_in_one-9.0.2.0-v0.1.6.ova',
  vcf_master_password: 'ChangeMe',
  vcf_mgmt_dhcp_ip: '10.105.42.1',
  vcf_mgmt_network_name: 'vcf_network',
  vcf_mgmt_network_vlan_id: '2197',
  vcf_mgmt_subnet_name: 'mgmt',
  vcf_subdomain: 'vcf',
  vmotion_network_id: '2658f685-1517-43ce-8973-e6435505962c',
  vmotion_subnet_id: 'b9b8ea36-13d0-4891-9466-e90bd557d2b0',
  vmotion_subnet_range: '10.105.44.0/24',
  vmotion_vlan_id: '2044',
  vsan_network_id: '9da037a3-6860-4d08-9261-3094b9e299bf',
  vsan_subnet_id: 'be6b78ff-4a96-452b-9821-7071d626e7a8',
  vsan_subnet_range: '10.105.45.0/24',
  vsan_vlan_id: '2045',
};

export const WORKLOAD_DOMAIN_TEMPLATE: Record<string, JsonValue> = {
  dns_create_records: true,
  esxi_install_timeout: '2100',
  lacp: false,
  openstack_auth_type: 'v3applicationcredential',
  openstack_endpoint_type: 'internal',
  openstack_identity_api_version: '3',
  overlay_subnet_range: '10.105.49.0/24',
  overlay_vlan_id: '2049',
  pairing_source: 'pci',
  vcf_external_network_id: '3f53dd45-0d9b-49d5-bf4d-c274f62e033c',
  vcf_overlay_network_id: '63ed4ef0-6be8-4279-8265-4769ea9f08de',
  vcf_overlay_subnet_id: '6b42d489-d264-4778-8375-4914d7046b7a',
  vcf_vmotion_network_id: '190b5a71-aa7a-4bbb-9687-bfea79d97d4f',
  vcf_vmotion_subnet_id: 'b41e2328-ef80-4692-a5d3-22baea429482',
  vcf_vsan_network_id: '8cb0fee6-9589-42f2-8cf5-7a7e9c206612',
  vcf_vsan_subnet_id: 'f9518eff-c94a-4e19-8eac-f2baf4a54b81',
  vmotion_subnet_range: '10.105.47.0/24',
  vmotion_vlan_id: '2047',
  vsan_subnet_range: '10.105.48.0/24',
  vsan_vlan_id: '2048',
  workload_domain_num: '1',
};

// JSON key -> vcfConfig row id, for the management domain. Keys omitted here
// (debug, dns_create_records, esxi_install_timeout, keycloak_request_*, lacp,
// openstack_*, pairing_source) have no customer-input row and keep the default.
export const MANAGEMENT_KEY_TO_ROW_ID: Record<string, string> = {
  appliance_password: 'vcf-mgmt-appliance-password',
  appliance_xapikey: 'vcf-mgmt-appliance-xapikey',
  bootstrap_dns_server: 'vcf-mgmt-bootstrap-dns-server',
  customer_network_dhcp_ip: 'vcf-mgmt-customer-network-dhcp-ip',
  customer_network_name: 'vcf-mgmt-customer-network-name',
  dns_server: 'vcf-mgmt-dns-server',
  dns_zone: 'vcf-mgmt-dns-zone',
  esxi_root_password: 'vcf-mgmt-esxi-root-password',
  esxi_setup_script: 'vcf-mgmt-esxi-setup-script',
  external_network_id: 'vcf-mgmt-external-network-id',
  flavor_name: 'vcf-mgmt-flavor-name',
  image_name: 'vcf-mgmt-image-name',
  keycloak_clusterissuer: 'vcf-mgmt-keycloak-clusterissuer',
  ntp_server: 'vcf-mgmt-ntp-server',
  overlay_network_id: 'vcf-mgmt-overlay-network-id',
  overlay_subnet_id: 'vcf-mgmt-overlay-subnet-id',
  overlay_subnet_range: 'vcf-mgmt-overlay-subnet-range',
  overlay_vlan_id: 'vcf-mgmt-overlay-vlan-id',
  vcf_deployer_ip: 'vcf-mgmt-vcf-deployer-ip',
  vcf_deployer_url: 'vcf-mgmt-vcf-deployer-url',
  vcf_master_password: 'vcf-mgmt-master-password',
  vcf_mgmt_dhcp_ip: 'vcf-mgmt-dhcp-ip',
  vcf_mgmt_network_name: 'vcf-mgmt-network-name',
  vcf_mgmt_network_vlan_id: 'vcf-mgmt-network-vlan-id',
  vcf_mgmt_subnet_name: 'vcf-mgmt-subnet-name',
  vcf_subdomain: 'vcf-mgmt-vcf-subdomain',
  vmotion_network_id: 'vcf-mgmt-vmotion-network-id',
  vmotion_subnet_id: 'vcf-mgmt-vmotion-subnet-id',
  vmotion_subnet_range: 'vcf-mgmt-vmotion-subnet-range',
  vmotion_vlan_id: 'vcf-mgmt-vmotion-vlan-id',
  vsan_network_id: 'vcf-mgmt-vsan-network-id',
  vsan_subnet_id: 'vcf-mgmt-vsan-subnet-id',
  vsan_subnet_range: 'vcf-mgmt-vsan-subnet-range',
  vsan_vlan_id: 'vcf-mgmt-vsan-vlan-id',
};

// JSON key -> vcfConfig row id, for the workload domain. Keys omitted here
// (dns_create_records, esxi_install_timeout, lacp, openstack_*, pairing_source)
// have no customer-input row and keep the default.
export const WORKLOAD_KEY_TO_ROW_ID: Record<string, string> = {
  overlay_subnet_range: 'vcf-wld-overlay-subnet-range',
  overlay_vlan_id: 'vcf-wld-overlay-vlan-id',
  vcf_external_network_id: 'vcf-wld-external-network-id',
  vcf_overlay_network_id: 'vcf-wld-overlay-network-id',
  vcf_overlay_subnet_id: 'vcf-wld-overlay-subnet-id',
  vcf_vmotion_network_id: 'vcf-wld-vmotion-network-id',
  vcf_vmotion_subnet_id: 'vcf-wld-vmotion-subnet-id',
  vcf_vsan_network_id: 'vcf-wld-vsan-network-id',
  vcf_vsan_subnet_id: 'vcf-wld-vsan-subnet-id',
  vmotion_subnet_range: 'vcf-wld-vmotion-subnet-range',
  vmotion_vlan_id: 'vcf-wld-vmotion-vlan-id',
  vsan_subnet_range: 'vcf-wld-vsan-subnet-range',
  vsan_vlan_id: 'vcf-wld-vsan-vlan-id',
  workload_domain_num: 'vcf-wld-workload-domain-num',
};

/**
 * Coerce a customer-typed answer to the JSON type of the template default so
 * booleans stay booleans (`"true"`/`"false"`) and numeric fields kept as
 * strings in the template stay strings (matching the reference JSON, where
 * VLAN ids and ranges are quoted).
 */
const coerceToTemplateType = (raw: string, templateValue: JsonValue): JsonValue => {
  if (typeof templateValue === 'boolean') {
    const normalized = raw.trim().toLowerCase();
    if (normalized === 'true') return true;
    if (normalized === 'false') return false;
    return templateValue;
  }
  return raw;
};

/**
 * Build a domain JSON object by overlaying the customer's answers onto the
 * default template. A key is overridden only when it maps to a row and the
 * customer supplied a non-empty (after trim) answer for that row.
 */
export const buildDomainJson = (
  template: Record<string, JsonValue>,
  keyToRowId: Record<string, string>,
  answers: Record<string, string>,
): Record<string, JsonValue> => {
  const result: Record<string, JsonValue> = { ...template };

  for (const [key, rowId] of Object.entries(keyToRowId)) {
    const raw = answers[rowId];
    if (raw === undefined || raw.trim() === '') continue;
    result[key] = coerceToTemplateType(raw, template[key]);
  }

  return result;
};

export type VcfDomain = 'management' | 'workload';

/** Build the domain JSON object for the requested VCF domain. */
export const buildVcfDomainJson = (
  domain: VcfDomain,
  answers: Record<string, string>,
): Record<string, JsonValue> =>
  domain === 'management'
    ? buildDomainJson(MANAGEMENT_DOMAIN_TEMPLATE, MANAGEMENT_KEY_TO_ROW_ID, answers)
    : buildDomainJson(WORKLOAD_DOMAIN_TEMPLATE, WORKLOAD_KEY_TO_ROW_ID, answers);
