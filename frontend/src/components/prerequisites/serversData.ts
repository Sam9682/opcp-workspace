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
    nodeUuid: 'c6adb16d-e6b6-445e-b61a-d1355c6c4abc',
    serialNumber: 'CZUD3K03LV',
    instanceUuid: '67bd41a3-d62a-45a2-9f14-8ac742e2de69',
    powerState: 'power on',
    provisionState: 'active',
    remark: '',
  },
  {
    nodeUuid: '5e88fcfb-60ee-45ad-94d7-1f957a78f614',
    serialNumber: 'CZUD3K03MH',
    instanceUuid: '708c8cb1-6877-42e8-9f0a-d00961bc5bd8',
    powerState: 'power on',
    provisionState: 'active',
    remark: '',
  },
  {
    nodeUuid: '640c4890-180a-4c03-ae97-36cde31bf645',
    serialNumber: 'CZUD3K03LC',
    instanceUuid: '',
    powerState: 'power off',
    provisionState: 'available',
    remark: '',
  },
  {
    nodeUuid: '96f4e575-dff9-4b36-af28-cb6d45fa7fad',
    serialNumber: 'CZUD3K03LH',
    instanceUuid: '2d0e13e1-39ef-43e2-beb7-f854bdb16235',
    powerState: 'power on',
    provisionState: 'active',
    remark: '',
  },
  {
    nodeUuid: 'e0a0ef95-c02f-4e7d-9aab-b7cfc34d80ca',
    serialNumber: 'CZUD3K03LK',
    instanceUuid: 'a3f12daa-c088-46f1-8246-814041357dbf',
    powerState: 'power on',
    provisionState: 'active',
    remark: '',
  },
  {
    nodeUuid: 'c43e588b-a12b-43b6-984e-01cb5a2579d6',
    serialNumber: 'CZUD3K03LM',
    instanceUuid: 'de5fc9a7-889c-49c0-b4fc-cdf176529fa6',
    powerState: 'power on',
    provisionState: 'active',
    remark: '',
  },
  {
    nodeUuid: '374bf65e-3b34-42c1-889d-391576218c8f',
    serialNumber: 'CZUD3K03LG',
    instanceUuid: '0fe58a1a-9cd3-4b53-ba83-2625ec10831d',
    powerState: 'power on',
    provisionState: 'active',
    remark: '',
  },
  {
    nodeUuid: '72b1fcb0-ebcd-4907-b4c6-1bb74cac093b',
    serialNumber: 'CZUD3K03L9',
    instanceUuid: 'a37c6215-8154-48b0-9769-b689993dd4c3',
    powerState: 'power on',
    provisionState: 'active',
    remark: '',
  },
  {
    nodeUuid: '895fa563-224a-4b3b-b38a-192720423f49',
    serialNumber: 'CZUD3K03LF',
    instanceUuid: '',
    powerState: 'None',
    provisionState: 'enroll',
    remark: 'Enrolled late (cable missing)',
  },
];
