// Server node inventory for the "Servers nodes" prerequisites tab.
//
// This is reference data collected from the OpenStack / Ironic inventory of the
// OPCP rack. It is displayed read-only on the Servers nodes tab so coordinators
// can pick an available Node UUID when filling in the CloudStore / Core Control
// Plane forms (see cloudStoreQuestionConfig, "pick the Node UUID of an
// available server, see Servers tab").
//
// A missing value in the source workbook (shown as "???" or blank) is stored as
// an empty string so the table renders a consistent placeholder.

export interface ServerNode {
  /** Ironic node UUID — the value referenced by CloudStore / Core Control Plane. */
  nodeUuid: string;
  /** Hardware serial number. */
  serialNumber: string;
  /** OpenStack instance UUID, or '' when the node has no active instance. */
  instanceUuid: string;
  /** Power state, e.g. "power on" / "power off" / "None". */
  powerState: string;
  /** Provision state, e.g. "active" / "available" / "enroll". */
  provisionState: string;
  /** Free-form remark. */
  remark: string;
}

export const SERVER_NODES: ReadonlyArray<ServerNode> = [
  {
    nodeUuid: '00000000-0000-0000-0000-000000000000',
    serialNumber: 'XXXXXXXXXX',
    instanceUuid: '',
    powerState: 'power off',
    provisionState: 'active',
    remark: '',
  },
  {
    nodeUuid: '00000000-0000-0000-0000-000000000000',
    serialNumber: 'XXXXXXXXXX',
    instanceUuid: '',
    powerState: 'power off',
    provisionState: 'active',
    remark: '',
  },
  {
    nodeUuid: '00000000-0000-0000-0000-000000000000',
    serialNumber: 'XXXXXXXXXX',
    instanceUuid: '',
    powerState: 'power off',
    provisionState: 'available',
    remark: '',
  },
  {
    nodeUuid: '00000000-0000-0000-0000-000000000000',
    serialNumber: 'XXXXXXXXXX',
    instanceUuid: '',
    powerState: 'power off',
    provisionState: 'active',
    remark: '',
  },
  {
    nodeUuid: '00000000-0000-0000-0000-000000000000',
    serialNumber: 'XXXXXXXXXX',
    instanceUuid: '',
    powerState: 'power off',
    provisionState: 'active',
    remark: '',
  },
  {
    nodeUuid: '00000000-0000-0000-0000-000000000000',
    serialNumber: 'XXXXXXXXXX',
    instanceUuid: '',
    powerState: 'power off',
    provisionState: 'active',
    remark: '',
  },
  {
    nodeUuid: '00000000-0000-0000-0000-000000000000',
    serialNumber: 'XXXXXXXXXX',
    instanceUuid: '',
    powerState: 'power off',
    provisionState: 'active',
    remark: '',
  },
  {
    nodeUuid: '00000000-0000-0000-0000-000000000000',
    serialNumber: 'XXXXXXXXXX',
    instanceUuid: '',
    powerState: 'power off',
    provisionState: 'active',
    remark: '',
  },
  {
    nodeUuid: '00000000-0000-0000-0000-000000000000',
    serialNumber: 'XXXXXXXXXX',
    instanceUuid: '',
    powerState: 'power off',
    provisionState: 'active',
    remark: '',
  },
];
