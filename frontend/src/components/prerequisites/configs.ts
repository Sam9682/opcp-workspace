import type { ContextConfig, FormConfig, QuestionFormConfig } from "./types";

// CloudStore page configuration.
// Derived directly from Requirement 4's seven reference sub-sections.
// Labels are in French; row `id`s are stable slugs, unique within the page.
export const cloudStoreConfig: FormConfig = {
  sections: [
    {
      id: "network-configuration",
      title: "Configuration réseau",
      rows: [
        { id: "network-name", label: "Nom du réseau" },
        { id: "subnet-name", label: "Nom du sous-réseau" },
        { id: "subnet-cidr", label: "CIDR du sous-réseau" },
        { id: "gateway-ip", label: "IP passerelle" },
        { id: "vlan-id", label: "VLAN ID" },
        { id: "dhcp-range", label: "Plage DHCP (10 IP exclues)" },
      ],
    },
    {
      id: "server-standalone",
      title: "Serveur (Standalone)",
      rows: [
        { id: "server-role", label: "Rôle" },
        { id: "server-hostname", label: "Nom d'hôte" },
        { id: "server-ip-address", label: "Adresse IP" },
        { id: "server-node-uuid", label: "Node UUID" },
        {
          id: "server-ingress-vip",
          label: "Ingress VIP (Cilium L2, statique)",
        },
        { id: "server-cluster-3-nodes", label: "Cluster 3 nœuds (optionnel)" },
        { id: "server-cluster-endpoint-vip", label: "VIP endpoint cluster" },
      ],
    },
    {
      id: "dns-configuration",
      title: "Configuration DNS",
      rows: [
        { id: "dns-zone-name", label: "Nom de zone DNS" },
        {
          id: "dns-delegation-target",
          label: "Cible de délégation (ingress VIP)",
        },
        { id: "dns-primary-server-ip", label: "IP serveur DNS primaire" },
        { id: "dns-fallback-server-ip", label: "IP serveur DNS de secours" },
      ],
    },
    {
      id: "ntp-configuration",
      title: "Configuration NTP",
      rows: [
        { id: "ntp-server-1-ip", label: "IP serveur NTP 1" },
        { id: "ntp-server-1-dns-name", label: "Nom DNS serveur NTP 1" },
        { id: "ntp-server-2-ip", label: "IP serveur NTP 2" },
        { id: "ntp-server-2-dns-name", label: "Nom DNS serveur NTP 2" },
      ],
    },
    {
      id: "security-certificates",
      title: "Sécurité & Certificats",
      rows: [{ id: "root-ca-certificate", label: "Certificat Root CA" }],
    },
    {
      id: "backup-s3",
      title: "Sauvegarde (S3)",
      rows: [
        { id: "backup-enabled", label: "Sauvegarde activée" },
        { id: "backup-s3-endpoint-url", label: "URL endpoint S3" },
        { id: "backup-s3-region", label: "Région" },
        { id: "backup-s3-bucket", label: "Bucket" },
        { id: "backup-s3-access-key", label: "Clé d'accès" },
        { id: "backup-s3-secret-key", label: "Clé secrète" },
        {
          id: "backup-path",
          label: "Chemin de sauvegarde",
          defaultValue: "cs-backups",
        },
      ],
    },
    {
      id: "client-side-actions",
      title: "Actions côté client",
      rows: [
        {
          id: "client-network-subnet-created",
          label: "Réseau/sous-réseau créé",
        },
        {
          id: "client-networks-wired-rack-edge",
          label: "Réseaux câblés vers l'edge du rack OPCP",
        },
        {
          id: "client-bastion-host-provisioned",
          label: "Hôte bastion provisionné",
        },
        { id: "client-bastion-access-provided", label: "Accès bastion fourni" },
        {
          id: "client-dns-zone-delegation-configured",
          label: "Délégation de zone DNS configurée",
        },
        {
          id: "client-s3-backup-bucket-reachable",
          label: "Bucket de sauvegarde S3 fourni et joignable",
        },
      ],
    },
  ],
};

// OPCP Core page configuration.
// PLACEHOLDER: inferred starter fields to be refined once the exact
// OPCP Core prerequisites are finalized (see design.md). Structurally
// identical to cloudStoreConfig so it reuses the shared TrackingForm.
export const opcpCoreConfig: FormConfig = {
  sections: [
    {
      id: "opcp-core-general-configuration",
      title: "Configuration générale",
      rows: [
        { id: "opcp-core-parameter-1", label: "Paramètre 1" },
        { id: "opcp-core-parameter-2", label: "Paramètre 2" },
        { id: "opcp-core-parameter-3", label: "Paramètre 3" },
      ],
    },
  ],
};

// LandingZone page configuration.
// PLACEHOLDER: inferred starter fields to be refined once the exact
// LandingZone prerequisites are finalized (see design.md). Structurally
// identical to cloudStoreConfig so it reuses the shared TrackingForm.
export const landingZoneConfig: FormConfig = {
  sections: [
    {
      id: "landingzone-configuration",
      title: "Configuration Landing Zone",
      rows: [
        { id: "landingzone-parameter-1", label: "Paramètre 1" },
        { id: "landingzone-parameter-2", label: "Paramètre 2" },
        { id: "landingzone-parameter-3", label: "Paramètre 3" },
      ],
    },
  ],
};

// ===========================================================================
// Question-archetype configs (QuestionFormConfig)
// ===========================================================================
// These four configs drive the new Question_Answer_Page archetype rendered by
// QuestionAnswerForm (a sibling of TrackingForm). Each row exposes two
// read-only question columns, a Mandatory/Optional marker, an example value,
// and a Comments/Details hint. The editable Client answer is persisted
// separately (see prerequisitesService / ClientAnswers).
//
// NOTE: All rows below are PLACEHOLDER/EXAMPLE scaffolding (Req 7.2). The
// definitive workbook question text and values will be supplied later and
// should replace these rows without changing the QuestionFormConfig shape.
// Row ids are stable and unique within each page (Req 7.3).
//
// NAMING NOTE: the legacy `cloudStoreConfig: FormConfig` above is still
// consumed by TrackingForm/CloudStorePage/TrackingForm.test.tsx and MUST keep
// its name until TrackingForm is retired (out of scope). The CloudStore
// question variant is therefore exported here as `cloudStoreQuestionConfig`.
// Task 8.2 retargets CloudStorePage to render QuestionAnswerForm with it.

// Network Checklist — deployment, shipping, network (control plane / OOB,
// data plane / edge, cross-DC WAN, network services) and service model.
// Rebuilt from the customer network checklist workbook. `mandatory` maps to
// the "Is it required for deployment?" column (Mandatory = true, Optional =
// false); `exampleValue` carries the recorded "Client answer" (blank when the
// answer was empty or still "???"). Row ids are stable and unique page-wide.
export const networkChecklistConfig: QuestionFormConfig = {
  sections: [
    {
      id: "nc-deployment",
      title: "1. Déploiement",
      rows: [
        {
          id: "nc-deploy-remote-access",
          questionPrimary:
            "Can we access OPCP racks remotely ? If yes, how ? (VPN, Bastion)",
          mandatory: false,
          exampleValue: "YES – NO",
        },
        {
          id: "nc-deploy-remote-access-provided",
          questionPrimary: "Remote access have been provided ?",
          mandatory: false,
          exampleValue: "YES – NO",
        },
        {
          id: "nc-deploy-site-access",
          questionPrimary: "How do we access deployment site ?",
          mandatory: true,
          exampleValue: "Remote access / Onsite access / No access",
        },
        {
          id: "nc-deploy-internet-access",
          questionPrimary: "On-site Internet access allowed ?",
          mandatory: false,
          exampleValue: "YES – NO",
        },
        {
          id: "nc-deploy-phone-calls",
          questionPrimary: "On-site phone calls allowed ?",
          mandatory: false,
          exampleValue: "YES – NO",
        },
        {
          id: "nc-deploy-own-laptop",
          questionPrimary: "Can technician use their own laptop ?",
          mandatory: false,
          exampleValue: "YES – NO",
        },
        {
          id: "nc-deploy-artifacts-delivery",
          questionPrimary:
            "Can OVH provide installation files (Artifacts) using their own devices (USB key, untrusted laptop) ? If not, what's the method to provide installation source files (if client provides USB key, must be USB 3.2 Gen1 and mini. 50Gb) ?",
          mandatory: true,
          exampleValue: "YES – NO",
        },
      ],
    },
    {
      id: "nc-shipping",
      title: "2. Livraison",
      rows: [
        {
          id: "nc-ship-racks-delivered",
          questionPrimary: "Are OPCP racks delivered ?",
          mandatory: true,
          exampleValue: "YES – NO",
        },
        {
          id: "nc-ship-racks-installed",
          questionPrimary: "Are OPCP racks installed ? (rack, power, cables)",
          mandatory: true,
          exampleValue: "YES – NO",
        },
        {
          id: "nc-ship-pv-recette",
          questionPrimary: "PV recette ?",
          mandatory: false,
          exampleValue: "YES – NO",
        },
      ],
    },
    {
      id: "nc-network-control-plane",
      title: "3a. Réseau — Control Plane / OOB",
      rows: [
        {
          id: "nc-cp-switch-10g",
          questionPrimary:
            "(Control plane/OOB) Is client switch capable of 10G (or 25G) ? 1 OOB uplink port for each controller + 1 port 1 GbE for each controller BMC",
          mandatory: true,
          exampleValue: "YES – NO",
          commentsHint:
            "Each OPCP Core Controller has an OOB uplink (25 GbE or 10 GbE, negotiated at 10 GbE according to your upstream capabilities) and a 1 GbE BMC port, both connected to the Customer Upstream OOB Network. NANOPOD: 1 controller; STANDARD POD / FABRIC: 3 controllers.",
        },
        {
          id: "nc-cp-sfp-lc-fiber",
          questionPrimary:
            "(Control plane/OOB) 10G-SR LC SFP Module are provided, are client switch's ports available with LC fiber and equivalent SFP module(s) ?",
          mandatory: true,
          exampleValue: "YES – NO",
        },
        {
          id: "nc-cp-oob-network-exists",
          questionPrimary:
            "Is OOB client network for control plane access exists ?",
          mandatory: true,
          exampleValue: "YES – NO",
        },
        {
          id: "nc-cp-oob-reachable",
          questionPrimary:
            "Is Control Plane (OOB) network reachable from deployment site ?",
          mandatory: true,
          exampleValue: "YES – NO",
        },
        {
          id: "nc-cp-ip-addressing",
          questionPrimary:
            "What is the planned IP addressing for control plane? (subnet, gateway, VLAN ID)",
          mandatory: true,
          exampleValue: "172.30.1.0/24 | GW 172.30.1.254 | VLAN 801",
          commentsHint:
            "Dedicated subnet for OPCP on the administration (OOB) network, with a default gateway; hosts the controllers and their VIP. Frozen at deployment (not editable after installation). Addressing and naming plan are entirely up to you.",
        },
        {
          id: "nc-cp-l2-untagged-vip",
          questionPrimary:
            "(Control plane/OOB) STANDARD POD / FABRIC: is a common untagged L2 network available between the 3 controllers (required for the shared VIP) ?",
          mandatory: true,
          exampleValue: "YES – NO – N/A (NANOPOD)",
          commentsHint:
            "The VIP shared by the three OPCP Core Controllers requires a common untagged L2 network between them. A prolonged outage of the customer OOB network can disrupt administrator access to the control plane (inter-controller data goes through the OPCP network). Not applicable to NANOPOD (single controller).",
        },
        {
          id: "nc-cp-mono-mode-transceivers",
          questionPrimary:
            "The link between OOB Control Plane Servers and the switch of the customer shall be in Mono Mode => Transceivers in Mono Mode",
          mandatory: true,
        },
      ],
    },
    {
      id: "nc-network-data-plane",
      title: "3b. Réseau — Data Plane / Edge",
      rows: [
        {
          id: "nc-dp-40-100g-support",
          questionPrimary:
            "(Data plane/Edge) Edge switches use 40/100G ports only, do client switches support these ?",
          mandatory: true,
          exampleValue: "YES – NO",
          commentsHint:
            "Fiber uplinks to the Customer Upstream Data Network run at 40 GbE or 100 GbE, according to the optics validated by OVHcloud. They are carried by the ToR switches in NANOPOD, and by the edge switches in STANDARD POD / FABRIC.",
        },
        {
          id: "nc-dp-mtu-9000",
          questionPrimary:
            "(Data plane/Edge) Can upstream ports facing the OPCP uplinks be configured with MTU 9000 (jumbo frames) ?",
          mandatory: true,
          exampleValue: "YES – NO",
          commentsHint:
            "OPCP customer-facing ports and uplinks use MTU 9000 (inter-switch links 9100). The MTU 1500 shown by Neutron is informational only. On bare-metal nodes, set MTU 9000 on the OS interfaces and prevent cloud-init / DHCP from restoring 1500 after reboot.",
        },
        {
          id: "nc-dp-physical-ports",
          questionPrimary:
            "(Data plane/Edge) How many physical ports you plan to use ?",
          mandatory: false,
        },
        {
          id: "nc-dp-lacp-aggregation",
          questionPrimary:
            "(Data plane/Edge) Is port aggregation (LACP only) necessary ?",
          mandatory: false,
        },
        {
          id: "nc-dp-edge-access-ports",
          questionPrimary:
            "(Data plane/Edge) How many edge access ports do you plan to use ?",
          mandatory: false,
        },
        {
          id: "nc-dp-edge-trunk-ports",
          questionPrimary:
            "(Data plane/Edge) How many edge trunk ports do you plan to use ?",
          mandatory: false,
          commentsHint:
            "Access mode: one Neutron network per uplink port, presented as standard 802.1Q. Trunk mode: several Neutron networks on one port, each with its own VLAN ID assigned by OPCP.",
        },
        {
          id: "nc-dp-qinq",
          questionPrimary:
            "(Data plane/Edge) Trunk mode: will instances push their own VLAN tags (802.1ad / QinQ) ? If yes, does the upstream equipment support double encapsulation ?",
          mandatory: false,
          exampleValue: "YES – NO – N/A",
          commentsHint:
            "In trunk mode the OPCP VLAN tag is preserved end to end: 802.1Q if instances do not use VLANs inside the Neutron network, 802.1ad (QinQ) if they do (OPCP VLAN = outer tag). Both can coexist on the same trunk.",
        },
      ],
    },
    {
      id: "nc-network-cross-dc-wan",
      title: "3c. Réseau — Cross-DC WAN / Inter-site",
      rows: [
        {
          id: "nc-wan-connection-type",
          questionPrimary:
            "Cross-DC WAN : what type of connection ? (Fiber, bandwidth, L2, etc)",
          mandatory: false,
          exampleValue: "YES - NO - N/A",
        },
        {
          id: "nc-wan-inter-site-ready",
          questionPrimary: "Cross-DC WAN : are inter-site connections ready ?",
          mandatory: false,
          exampleValue: "YES - NO - N/A",
        },
        {
          id: "nc-wan-max-latency",
          questionPrimary:
            "Cross-DC WAN: what is the maximum acceptable latency between sites?",
          mandatory: false,
          exampleValue: "YES - NO - N/A",
        },
      ],
    },
    {
      id: "nc-network-services",
      title: "3d. Services réseau (DNS, NTP, Proxy)",
      rows: [
        {
          id: "nc-svc-dns-servers",
          questionPrimary:
            "Are internal DNS servers available? If yes, provide IPs.",
          mandatory: false,
          exampleValue: "YES - NO",
          commentsHint:
            "Resolvers are only needed if OPCP must resolve external FQDNs (S3, LDAP…). Flow: OPCP administration network -> DNS resolvers, UDP/53. Can be omitted for an air-gapped platform configured by IP.",
        },
        {
          id: "nc-svc-dns-delegation",
          questionPrimary:
            "Which domain will be delegated to OPCP, and can a forwarder be created from internal DNS resolvers to the OPCP VIP ?",
          mandatory: true,
          exampleValue: "opcp01.exemple.com",
          commentsHint:
            "Every query for *.<domain> must be forwarded to the OPCP VIP. Flow: customer DNS resolvers -> OPCP VIP, UDP/53 and TCP/53. Not editable after installation.",
        },
        {
          id: "nc-svc-ntp-servers",
          questionPrimary:
            "Are NTP servers available? If yes, provide IPs or FQDNs.",
          mandatory: true,
          exampleValue: "YES - NO",
          commentsHint:
            "Mandatory: at least one NTP source reachable from the OPCP administration network. Flow: UDP/123.",
        },
        {
          id: "nc-svc-http-proxy",
          questionPrimary:
            "Is an HTTP/HTTPS proxy required for Internet access? If yes, provide address.",
          mandatory: false,
          exampleValue: "YES - NO",
          commentsHint:
            "OPCP is designed to run air-gapped: none of the platform flows requires Internet access; the only expected destinations are services of your own information system.",
        },
        {
          id: "nc-svc-firewall-rules",
          questionPrimary:
            "Are firewall rules to be opened for platform operation? (flow list provided by OVHcloud)",
          mandatory: true,
          exampleValue: "YES - NO",
          commentsHint:
            "All flows are on the OPCP administration (OOB) network, none on the data network. Inbound: admin workstations / users -> controllers VIP TCP/443 (OpenStack API, Horizon); admins -> controllers TCP/22 SSH (Self-managed only). Outbound from the OPCP administration network: NTP UDP/123 (mandatory); DNS UDP/53 (optional); Syslog UDP/514 or TCP/514 (recommended); S3 backup TCP/443 (recommended); S3 long-term metrics TCP/443 (recommended); LDAPS TCP/636 (optional).",
        },
        {
          id: "nc-svc-syslog-server",
          questionPrimary:
            "Is a centralized Syslog server available to receive logs?",
          mandatory: false,
          exampleValue: "YES - NO",
          commentsHint:
            "Recommended. Flow: UDP/514 or TCP/514. Without external syslog, logs are kept locally for 7 days / 50 GB max.",
        },
      ],
    },
    {
      id: "nc-service-models",
      title: "4. Modèles de service",
      rows: [
        {
          id: "nc-service-model-type",
          questionPrimary:
            "Self-managed or Fully managed by OVHcloud ? If Fully managed, fill in the IPsec interconnection (Core Control Plane tab)",
          mandatory: true,
          exampleValue: "Self-managed - Fully managed by OVHcloud",
          commentsHint:
            "Self-managed: the customer operates the Core (control plane) and application services, no interconnection to OVHcloud. Fully managed by OVHcloud: OVHcloud operates them remotely through a site-to-site IPsec tunnel. In both modes, what you deploy on top of OPCP (VMs, containers, bare-metal, data) remains your responsibility.",
        },
        {
          id: "nc-service-topology",
          questionPrimary:
            "Which deployment topology ? NANOPOD / STANDARD POD / FABRIC",
          mandatory: true,
          exampleValue: "NANOPOD - STANDARD POD - FABRIC",
          commentsHint:
            "NANOPOD: 1 controller (no control plane redundancy), 1 rack, no spine/edge, data network on the ToR. STANDARD POD: 3 controllers, 2 to 3 racks, edges only. FABRIC: 3 controllers, 3 to 10 racks (more with megaspine), spine + edges. In STANDARD POD / FABRIC the data network is configured on the edges.",
        },
      ],
    },
  ],
};

// Core Control Plane — OPCP control plane service configuration (interconnection,
// network, certificates, NTP/DNS, syslog, backup, metrics, LDAP, SSH).
// Aligned with the OVHcloud guide "Prérequis techniques pour le déploiement"
// (docs.ovhcloud.com/fr/guides/hosted-private-cloud/opcp/opcp-prerequisites,
// last updated 2026-11-23). Each prerequisite is one row: `questionPrimary` =
// prerequisite, `questionSecondary` = associated network flow (omitted when the
// configuration is local to OPCP), `commentsHint` = description, items to
// provide and whether it is editable after installation, `exampleValue` = the
// guide's generic example. `mandatory` follows the guide's "Obligatoire"
// column ("Optionnel" / "Optionnel mais recommandé" = false). Row ids are
// stable (persistence keys) and unique page-wide.
// Formerly "OPCP Core".
export const coreControlPlaneConfig: QuestionFormConfig = {
  sections: [
    {
      id: "ccp-services",
      title: "Services du Control Plane",
      rows: [
        {
          id: "ccp-managed-interconnection",
          questionPrimary: "Managed OPCP interconnection (IPsec)",
          questionSecondary:
            "Customer IPsec endpoint <-> OVHcloud — site-to-site IPsec tunnel",
          mandatory: true,
          commentsHint:
            'Mandatory in "Fully managed by OVHcloud" mode only (N/A in Self-managed). Used for remote operation and support. Provide: public IP of your IPsec endpoint, client-side subnet exposed in the tunnel (typically the OPCP administration subnet), pre-shared key (PSK) — sent over a secure channel agreed with your OVHcloud contact. Default parameters: IKEv2 only (IKEv1 not supported), PSK authentication, AES-256, SHA-256, DH group 14, PFS enabled. Going below AES-256 is discouraged (last resort only). Editable after installation: Yes.',
          exampleValue:
            "Endpoint 203.0.113.10 | Subnet 172.30.1.0/24 | PSK via secure channel",
        },
        {
          id: "ccp-network",
          questionPrimary: "Administration network",
          mandatory: true,
          commentsHint:
            "Management (OOB) network on which OPCP is placed. Hosts the controllers and their VIP, and is the source of outbound flows to your internal services (NTP, DNS, syslog, S3, LDAP). Provide: subnet allocated to OPCP + default gateway. Editable after installation: NO — frozen at deployment, any change requires a full reinstall.",
          exampleValue: "172.30.1.0/24 | GW 172.30.1.254",
        },
        {
          id: "ccp-variables",
          questionPrimary: "OPCP environment variables",
          mandatory: true,
          commentsHint:
            "Variables uniquely identifying the deployment, reused in Netbox, logs, monitoring and other components. Provide a value for each: env (logical environment id), region (region / geographic zone code), stage (lifecycle stage), org (owning organization), site (physical site id), location (precise location within the site). No naming convention is imposed by OVHcloud. Editable after installation: NO.",
          exampleValue:
            "env=opcp-prod-0 | region=par | stage=prod | org=mycompany | site=dc1 | location=R11-1",
        },
        {
          id: "ccp-server-names",
          questionPrimary: "Controller names & IP addresses (+ VIP)",
          mandatory: true,
          commentsHint:
            "For each OPCP Core Controller: hostname (FQDN or short name) + IP address on the administration network. In 3-controller configuration (STANDARD POD / FABRIC), also provide the VIP shared by the three nodes — single entry point to the OpenStack APIs and Horizon (NANOPOD: 1 controller, no VIP). Editable after installation: NO.",
          exampleValue:
            "opcp-controller-0 / 172.30.1.10 | opcp-controller-1 / 172.30.1.11 | opcp-controller-2 / 172.30.1.12 | VIP opcp.exemple.com / 172.30.1.5",
        },
        {
          id: "ccp-certificates",
          questionPrimary: "Certificates",
          mandatory: true,
          commentsHint:
            "Valid TLS certificates for OPCP interfaces (OpenStack API, Horizon, internal services). Choose one option before deployment: (A — recommended) Intermediate CA provided by the customer, derived from your internal PKI -> provide the intermediate CA certificate + its private key (over a secure channel); rotation of issued certificates managed by CertManager. (B) Self-signed CA generated by OPCP -> nothing to provide, rotation managed by CertManager; the OPCP root certificate must then be distributed to your clients to avoid security warnings. Any public exposure of OPCP must go through a reverse proxy (out of OPCP scope) carrying public certificates. Editable after installation: Yes.",
          exampleValue:
            "Option A (customer intermediate CA) – Option B (OPCP self-signed CA)",
        },
        {
          id: "ccp-ntp",
          questionPrimary: "NTP",
          questionSecondary:
            "OPCP administration network -> Customer NTP servers — UDP/123",
          mandatory: true,
          commentsHint:
            "Reliable time source required by all components (log consistency, certificate validity, quorum election…). Provide one or more NTP server IP addresses, or DNS names if DNS resolution is configured. Open UDP/123 from the OPCP administration network. Editable after installation: Yes.",
          exampleValue:
            "172.30.1.200 / ntp1.exemple.com, 172.30.1.201 / ntp2.exemple.com",
        },
        {
          id: "ccp-dns",
          questionPrimary: "DNS — domain delegation",
          questionSecondary:
            "Customer DNS resolvers -> OPCP VIP — UDP/53 + TCP/53",
          mandatory: true,
          commentsHint:
            "OPCP exposes its interfaces through FQDNs under a domain delegated to it. Provide the domain name allocated to this OPCP platform, and create a forwarder from your internal DNS resolvers to the OPCP VIP so that every query for *.<domain> is resolved by OPCP. Editable after installation: NO (the forwarder can be adapted as long as FQDNs remain stable).",
          exampleValue: "opcp01.exemple.com",
        },
        {
          id: "ccp-dns-resolvers",
          questionPrimary: "DNS resolvers — external resolution",
          questionSecondary:
            "OPCP administration network -> Customer DNS resolvers — UDP/53",
          mandatory: false,
          commentsHint:
            "Optional. Only needed if OPCP must resolve external FQDNs (S3 endpoint for backup / long-term metrics, LDAP directory…). Provide the IP address of one or more resolvers. Can be omitted for a strictly air-gapped platform configured by IP. Editable after installation: Yes.",
          exampleValue: "172.30.1.100, 172.30.1.101",
        },
        {
          id: "ccp-syslog-servers",
          questionPrimary: "Syslog — log centralization",
          questionSecondary:
            "OPCP administration network -> Customer Syslog — UDP/514 or TCP/514",
          mandatory: false,
          commentsHint:
            "Optional but recommended. Provide: syslog server IP address or FQDN, listening port, protocol (TCP or UDP). Without external syslog, logs are kept locally with a default retention of 7 days and 50 GB max (oldest logs deleted beyond that) — configure an external syslog for any longer compliance retention. Editable after installation: Yes.",
          exampleValue: "172.30.1.250 | 514 | UDP",
        },
        {
          id: "ccp-backup",
          questionPrimary: "Backup — S3 endpoint",
          questionSecondary:
            "OPCP administration network -> Customer S3 — TCP/443",
          mandatory: false,
          commentsHint:
            'Optional but very strongly recommended for production: without external backup there is no restore mechanism after a major incident. Backs up infrastructure state (configurations, control plane state, metadata). Provide: S3 endpoint, access key, secret key (over a secure channel), two DISTINCT bucket names — one for Velero backups (persistent volumes, PV) and one for CNPG backups (databases, DB); Velero rejects a bucket that also holds DB backups and its backup storage location stays "Unavailable" — and the S3 region name. Editable after installation: Yes.',
          exampleValue:
            "s3.exemple.com:443 | PV bucket opcp01-backup-pv-dc1 | DB bucket opcp01-backup-db-dc1 | region paris",
        },
        {
          id: "ccp-long-term-metrics",
          questionPrimary: "Long-term metrics storage — S3 endpoint",
          questionSecondary:
            "OPCP administration network -> Customer S3 — TCP/443",
          mandatory: false,
          commentsHint:
            "Optional but recommended. Keeps platform metrics beyond the local retention window. Provide: S3 endpoint, access key, secret key, bucket name dedicated to metrics (must be distinct from the backup buckets), region name. The same S3 endpoint and credentials as for backup can be reused, with a different bucket. Editable after installation: Yes.",
          exampleValue:
            "s3.exemple.com:443 | bucket opcp01-metrics-dc1 | region paris",
        },
        {
          id: "ccp-ldap",
          questionPrimary: "LDAP",
          questionSecondary:
            "OPCP administration network -> Customer AD / IdP — TCP/636 (LDAPS)",
          mandatory: false,
          commentsHint:
            "Optional. Identity federation of the OPCP embedded Keycloak with your corporate directory (Active Directory or other LDAP server). Provide: IP addresses or FQDNs of the LDAP servers + listening port (typically 636 for LDAPS). Without federation, users are managed directly in the embedded Keycloak. Editable after installation: Yes.",
          exampleValue: "ldap.exemple.com, 10.3.0.5, 10.3.0.6 | 636",
        },
        {
          id: "ccp-ssh-public-key",
          questionPrimary: "SSH public key",
          mandatory: false,
          commentsHint:
            "Optional but recommended. One or more customer administrators' SSH public keys, used to access the OPCP controllers after bootstrap (opcp-cli, opcp-diag). In Fully managed mode, it gives the customer access to the administration tools in addition to OVHcloud teams. If none is provided, a new SSH key pair is generated during deployment. Editable after installation: Yes.",
          exampleValue: "ssh-ed25519 AAAA… admin@mycompany",
        },
      ],
    },
  ],
};

// CloudStore (question variant) — network, servers, DNS, NTP, certificates,
// backup, client actions. Exported as `cloudStoreQuestionConfig` to avoid a
// collision with the legacy `cloudStoreConfig: FormConfig` above.
// Rebuilt from the customer CloudStore workbook. Mapping: `questionPrimary` =
// Service, `questionSecondary` = Direction (omitted when "N/A"),
// `exampleValue` = the workbook's proposed "Client's answers", and
// `commentsHint` = Description plus the Service Access and "Editable after
// installation" columns (folded in, since the row model has no dedicated
// fields for them). `mandatory` maps the Mandatory column ("Yes" = true,
// "Optional"/"Optional but recommended" = false). Row ids are stable and
// unique page-wide.
export const cloudStoreQuestionConfig: QuestionFormConfig = {
  sections: [
    {
      id: "cs-network",
      title: "1. Configuration réseau",
      rows: [
        {
          id: "cs-network-subnet-creation",
          questionPrimary: "Network & Subnet creation",
          mandatory: true,
          exampleValue:
            "Network Name: CLOUDSTORE | Subnet Name: | Subnet CIDR: 172.18.1.0/24 | Gateway IP: 172.18.1.254 | VLAN ID: 800 | DHCP range: 172.18.1.15-172.18.1.253",
          commentsHint:
            "A dedicated OpenStack network with a subnet must be created prior to deployment. The subnet connects via edge gateways to the customer's network and allows access to the CloudStore UI. Requirements: DHCP must be enabled on the subnet; at least 10 IPs must be excluded from the DHCP range for static CloudStore assignment. If VLAN is required, add: --provider-network-type vlan --provider-segment <VLAN_ID>. [Editable after installation: No]",
        },
        {
          id: "cs-network-wiring-edge",
          questionPrimary: "Network wiring to OPCP rack edge",
          mandatory: true,
          exampleValue: "Already Connected for OPCP Core. TO BE CONFIRMED !",
          commentsHint:
            "The created networks must be wired up to the edge of the OPCP rack so they connect to the customer's networks. [Editable after installation: No]",
        },
      ],
    },
    {
      id: "cs-servers",
      title: "2. Informations serveur",
      rows: [
        {
          id: "cs-node-standalone",
          questionPrimary: "Node (standalone deployment)",
          mandatory: true,
          exampleValue:
            "Hostname: opcp-demo-cloudstore-MYCOMPANY-0-1 (proposed) | IP Address: 172.18.1.6 (static IP outside DHCP range, proposed) | Node UUID: (pick the Node UUID of an available server, see Servers tab)",
          commentsHint:
            "The hostname, IP address and node UUID must be collected for each node. The IP addresses must be chosen from the static IP range (outside the DHCP pool). [Editable after installation: No]",
        },
        {
          id: "cs-ingress-vip",
          questionPrimary: "Ingress VIP (customer)",
          mandatory: true,
          exampleValue:
            "Ingress VIP: 172.18.1.13 (proposed, static IP outside DHCP range, distinct from node IP and gateway)",
          commentsHint:
            "CloudStore exposes its services (UI, API, …) on a virtual IP of the customer subnet (announced in L2 by Cilium). This ingress VIP is required for every deployment, including standalone. It must be a free static IP in the customer subnet, distinct from the node IP, the gateway and the DHCP pool. [Editable after installation: No]",
        },
        {
          id: "cs-ha-3-node",
          questionPrimary: "High Availability (3-node) deployment",
          mandatory: false,
          exampleValue:
            "Hostname(s): e.g. cloudstore-0, cloudstore-1, cloudstore-2 | IP Address(es): static IP for each node | Node UUID(s): OpenStack UUID for each server | Cluster-endpoint VIP: future HA only, not used today",
          commentsHint:
            "Kubernetes HA is not yet available for CloudStore. The cluster-endpoint VIP is only used once HA is released — not used today. Some customers may wish to pre-reserve hostnames, IPs and the cluster VIP in advance. Note: The Ingress VIP above is always required, regardless of HA. [Mandatory: Optional (future HA)] [Editable after installation: No]",
        },
      ],
    },
    {
      id: "cs-dns",
      title: "3. Configuration DNS",
      rows: [
        {
          id: "cs-dns-zone-delegation",
          questionPrimary: "DNS zone delegation",
          questionSecondary: "Customer DNS Servers -> CloudStore ingress VIP",
          mandatory: true,
          exampleValue:
            "See delegation in « Core Control Plane » tab | DNS Zone Name: ???????? | Delegation Target: ???????? (the CloudStore customer ingress VIP)",
          commentsHint:
            "The customer must provide the name of the DNS zone for delegation. This zone must be delegated to the CloudStore customer ingress VIP. [Service Access: UDP/53] [Editable after installation: No]",
        },
        {
          id: "cs-dns-resolver-config",
          questionPrimary: "DNS resolver configuration",
          questionSecondary: "CloudStore -> Customer DNS resolvers",
          mandatory: true,
          exampleValue:
            "See resolver in « Core Control Plane » tab | Primary DNS Server IP: ???????? | Fallback DNS Server IP: ????????",
          commentsHint:
            "The IP addresses of the DNS servers to use for name resolution. [Service Access: UDP/53] [Editable after installation: Yes]",
        },
      ],
    },
    {
      id: "cs-ntp",
      title: "4. Configuration NTP",
      rows: [
        {
          id: "cs-ntp",
          questionPrimary: "NTP",
          questionSecondary: "CloudStore -> Customer NTP",
          mandatory: true,
          exampleValue:
            "See NTP in « Core Control Plane » tab | NTP Server IP / FQDN: ???????? | NTP DNS Name: ???????? (if applicable)",
          commentsHint:
            "The NTP servers to be used for time synchronization, including their IP addresses and associated DNS names where applicable. NTP is configured at the OPCP level (ntp.servers) and shared with CloudStore. [Service Access: UDP/123] [Editable after installation: Yes]",
        },
      ],
    },
    {
      id: "cs-certificates",
      title: "5. Certificats",
      rows: [
        {
          id: "cs-root-ca",
          questionPrimary: "Root CA certificate",
          mandatory: true,
          exampleValue:
            "See certificates in « Core Control Plane » tab | opcp01-demo.MYCOMPANY.ma | <Root CA certificate to be provided by secure method>",
          commentsHint:
            "The customer must provide their Root CA certificate, which is used to generate the CloudStore certificates. It populates the customer_ca_crt / customer_ca_key secrets. The Root CA must be provided by the customer before deployment begins. [Editable after installation: To confirm]",
        },
      ],
    },
    {
      id: "cs-backup",
      title: "6. Stockage de sauvegarde (S3)",
      rows: [
        {
          id: "cs-s3-backup",
          questionPrimary: "S3 Backup storage",
          questionSecondary: "CloudStore -> Customer S3",
          mandatory: false,
          exampleValue:
            "S3 endpoint URL: e.g. s3-luxembourg.obj.example.com | S3 region: e.g. luxembourg | S3 bucket: … | S3 access key: <to be given by secure method> | S3 secret key: <to be given by secure method> | Backup path: default cs-backups",
          commentsHint:
            "If CloudStore backups are enabled, the customer provides an S3 bucket dedicated to backups. The bucket must be reachable from the customer network. The access key and secret key are not stored in the config file: they go into the deployment secrets (opcp-cli secrets passwords --edit). The endpoint, region, bucket and backup path are set in the cloudstore.config block. [Mandatory: Optional but recommended] [Service Access: TCP/443] [Editable after installation: Yes]",
        },
      ],
    },
    {
      id: "cs-client-actions",
      title: "7. Actions côté client",
      rows: [
        {
          id: "cs-bastion-host",
          questionPrimary: "Bastion host",
          mandatory: true,
          exampleValue:
            "Done during « Core Control Plane » installation | Bastion host: … | Access credentials: <to be given by secure method> | Connection details: …",
          commentsHint:
            "The customer must provision a bastion host and provide the necessary access credentials and connection details. This is required so that our team can reach the CloudStore UI after installation to carry out validation and testing. [Editable after installation: Yes]",
        },
        {
          id: "cs-dns-delegation-client-action",
          questionPrimary: "DNS zone delegation (client action)",
          mandatory: true,
          exampleValue:
            "Done during « Core Control Plane » installation | Confirmed: Yes / No",
          commentsHint:
            "The customer must configure the DNS zone delegation before post-installation tests are performed. The zone must be delegated to the CloudStore customer ingress VIP (ingress_vips.customer). [Editable after installation: N/A]",
        },
      ],
    },
  ],
};

// VCF — full customer-input parameter set from the CloudStore VCF workbook.
// Mapping: `questionPrimary` = the exact parameter name (e.g. vcf_mgmt_network_name),
// `questionSecondary` = human description, `exampleValue` = the workbook "Value"
// (omitted when the workbook left it blank), and `commentsHint` = any
// "Example:" text and notes. Row ids are domain-prefixed (`vcf-mgmt-*` /
// `vcf-wld-*`) so parameter names that repeat across domains stay unique
// page-wide. `mandatory = false` for the CloudStore-provided host params
// (node_uuids / bootstrap_node_uuids — no customer input), the four Passwords
// & Secrets rows (generated when empty) and `esxi_setup_script` (non-Broadcom
// hardware only); every other parameter is mandatory.
export const vcfConfig: QuestionFormConfig = {
  sections: [
    {
      id: "vcf-mgmt-hosts",
      title: "Domaine de management — Hôtes",
      rows: [
        {
          id: "vcf-mgmt-node-uuids",
          questionPrimary: "node_uuids (management)",
          questionSecondary:
            "Baremetal node uuids of the vcf_mgmt pool (JSON list as string). Minimum 4 nodes for the management domain.",
          mandatory: false,
          commentsHint:
            'Example: "91acc6a3-b8ae-4c15-918b-917b3902d1df", "1533e7bc-8122-499c-b5e7-55298b318305". Provided by the CloudStore from the node selection — not filled by hand; keep default, no customer input required.',
        },
        {
          id: "vcf-mgmt-bootstrap-node-uuids",
          questionPrimary: "bootstrap_node_uuids",
          questionSecondary:
            "Bootstrap pool node uuids (JSON list as string). Only the first is used; the list must contain at least one uuid.",
          mandatory: false,
          commentsHint:
            'Example: "f6df4020-3e39-4635-a82e-c52765d04504". Provided by the CloudStore from the node selection — not filled by hand; keep default, no customer input required.',
        },
      ],
    },
    {
      id: "vcf-mgmt-network",
      title: "Domaine de management — Réseau",
      rows: [
        {
          id: "vcf-mgmt-network-name",
          questionPrimary: "vcf_mgmt_network_name",
          questionSecondary:
            "VCF Network — an already created neutron network with 9000 MTU.",
          mandatory: true,
          exampleValue: "VCF-MGT (beeb7852-2ae5-47eb-bc87-eaa508c8d49c)",
          commentsHint: "Example: vcf_network",
        },
        {
          id: "vcf-mgmt-subnet-name",
          questionPrimary: "vcf_mgmt_subnet_name",
          questionSecondary:
            "Management subnet for VCF — an existing /22 subnet with DHCP activated and an allocation pool on the /23 part of the range.",
          mandatory: true,
          exampleValue:
            "VCF_MGT-subnet (172.18.2.0/22 : start=172.18.2.2, end=172.18.2.254)",
          commentsHint:
            "Example: mgmt. E.g. if the range is 10.105.60.0/22, the allocation pool should be from 10.105.62.1 to 10.105.63.250.",
        },
        {
          id: "vcf-mgmt-network-vlan-id",
          questionPrimary: "vcf_mgmt_network_vlan_id",
          questionSecondary:
            "VCF Network VLAN ID — must match the VLAN set on vcf_mgmt_network.",
          mandatory: true,
          exampleValue: "801",
          commentsHint: "Example: 2040",
        },
        {
          id: "vcf-mgmt-dhcp-ip",
          questionPrimary: "vcf_mgmt_dhcp_ip",
          questionSecondary:
            "IP of the DHCP on the VCF management subnet. Used as a gateway during esxi install to get the ks.cfg as user-data.",
          mandatory: true,
          exampleValue: "172.18.3.2",
          commentsHint: "Example: 10.105.40.1",
        },
        {
          id: "vcf-mgmt-customer-network-name",
          questionPrimary: "customer_network_name",
          questionSecondary:
            "Customer Network name — the network on which the CloudStore is deployed; the bootstrap machine will have an IP address on it.",
          mandatory: true,
          exampleValue: "CLOUDSTORE",
          commentsHint: "Example: customerapi-network",
        },
        {
          id: "vcf-mgmt-customer-network-dhcp-ip",
          questionPrimary: "customer_network_dhcp_ip",
          questionSecondary:
            "IP of the DHCP on the CloudStore network. Used as a gateway during esxi install to get the ks.cfg as user-data.",
          mandatory: true,
        },
        {
          id: "vcf-mgmt-external-network-id",
          questionPrimary: "external_network_id",
          questionSecondary:
            "User network id — the dedicated external network carrying the NSX north-south (Tier-0) uplinks and customer workload traffic. Bound to grp2 of each VCF host and carried by the user-vds. Must exist before deployment.",
          mandatory: true,
          exampleValue: "1f380d53-4d31-43e9-8051-69081f7232ba",
          commentsHint:
            "The TOR uses a Q-in-Q tunnel, so every VLAN tagged from that dvs is encapsulated and no per-VLAN neutron network is needed.",
        },
        {
          id: "vcf-mgmt-vmotion-network-id",
          questionPrimary: "vmotion_network_id",
          questionSecondary:
            "vMotion network id — a network used for vMotion connectivity inside its own vlan.",
          mandatory: true,
          exampleValue: "ec8a53ec-726f-4dfb-b106-53495c7a0dd9",
        },
        {
          id: "vcf-mgmt-vmotion-subnet-id",
          questionPrimary: "vmotion_subnet_id",
          questionSecondary: "vMotion subnet id — a subnet with a /24.",
          mandatory: true,
        },
        {
          id: "vcf-mgmt-vmotion-subnet-range",
          questionPrimary: "vmotion_subnet_range",
          questionSecondary: "The /24 range defined on the vMotion subnet.",
          mandatory: true,
          exampleValue: "172.18.5.0/24",
          commentsHint: "Example: 10.105.44.0/24",
        },
        {
          id: "vcf-mgmt-vmotion-vlan-id",
          questionPrimary: "vmotion_vlan_id",
          questionSecondary:
            "VLAN to isolate vMotion traffic — must match the VLAN set on vmotion_network.",
          mandatory: true,
          exampleValue: "803",
          commentsHint: "Example: 2044",
        },
        {
          id: "vcf-mgmt-vsan-network-id",
          questionPrimary: "vsan_network_id",
          questionSecondary:
            "vSAN network id — a network used for vSAN connectivity inside its own vlan.",
          mandatory: true,
          exampleValue: "1eb70c30-2096-48d6-b087-a588cf1fda47",
        },
        {
          id: "vcf-mgmt-vsan-subnet-id",
          questionPrimary: "vsan_subnet_id",
          questionSecondary: "vSAN subnet id — a subnet with a /24.",
          mandatory: true,
        },
        {
          id: "vcf-mgmt-vsan-subnet-range",
          questionPrimary: "vsan_subnet_range",
          questionSecondary: "The /24 range defined on the vSAN subnet.",
          mandatory: true,
          exampleValue: "172.18.6.0/24",
          commentsHint: "Example: 10.105.45.0/24",
        },
        {
          id: "vcf-mgmt-vsan-vlan-id",
          questionPrimary: "vsan_vlan_id",
          questionSecondary:
            "VLAN to isolate vSAN traffic — must match the VLAN set on vsan_network.",
          mandatory: true,
          exampleValue: "804",
          commentsHint: "Example: 2045",
        },
        {
          id: "vcf-mgmt-overlay-network-id",
          questionPrimary: "overlay_network_id",
          questionSecondary:
            "overlay network id — a network used for overlay connectivity inside its own vlan.",
          mandatory: true,
          exampleValue: "a0de5d63-6219-4985-9213-d90fc10dd9b3",
        },
        {
          id: "vcf-mgmt-overlay-subnet-id",
          questionPrimary: "overlay_subnet_id",
          questionSecondary: "overlay subnet id.",
          mandatory: true,
        },
        {
          id: "vcf-mgmt-overlay-subnet-range",
          questionPrimary: "overlay_subnet_range",
          questionSecondary: "The /24 range defined on the overlay subnet.",
          mandatory: true,
          exampleValue: "172.18.4.0/24",
          commentsHint: "Example: 10.105.46.0/24",
        },
        {
          id: "vcf-mgmt-overlay-vlan-id",
          questionPrimary: "overlay_vlan_id",
          questionSecondary:
            "VLAN to isolate overlay traffic — must match the VLAN set on overlay_network.",
          mandatory: true,
          exampleValue: "802",
          commentsHint: "Example: 2046",
        },
      ],
    },
    {
      id: "vcf-mgmt-dns",
      title: "Domaine de management — DNS",
      rows: [
        {
          id: "vcf-mgmt-dns-zone",
          questionPrimary: "dns_zone",
          questionSecondary: "The CloudStore DNS Zone.",
          mandatory: true,
          exampleValue: "cs01.MYCOMPANY.ma",
          commentsHint: "Example: staging.cloudstore.ovh",
        },
        {
          id: "vcf-mgmt-dns-server",
          questionPrimary: "dns_server",
          questionSecondary:
            "CloudStore DNS Server address reachable from the vcf mgt network (reachable CloudStore DNS, or a nameserver with proper delegation).",
          mandatory: true,
          exampleValue: "172.27.0.1 & 172.27.0.2",
          commentsHint:
            "Delegation must be configured for the cloudstore dns_zone and the reverse zone corresponding to the range of the vcf management subnet.",
        },
        {
          id: "vcf-mgmt-bootstrap-dns-server",
          questionPrimary: "bootstrap_dns_server",
          questionSecondary:
            "CloudStore DNS Server address reachable from the cloudstore network — should be the same as dns_server and bears the same constraints.",
          mandatory: true,
          exampleValue: "172.27.0.1",
        },
      ],
    },
    {
      id: "vcf-mgmt-auth",
      title: "Domaine de management — Authentification & OpenStack",
      rows: [
        {
          id: "vcf-mgmt-image-name",
          questionPrimary: "image_name",
          questionSecondary:
            "ESXi Glance image name (see creation instructions).",
          mandatory: true,
          exampleValue: "esxi-9.0.2-user-data",
          commentsHint: "Example: esxi-9.0.1-user-data",
        },
        {
          id: "vcf-mgmt-flavor-name",
          questionPrimary: "flavor_name",
          questionSecondary: "Flavor name created for vcf.",
          mandatory: true,
          exampleValue: "vcf-flavor",
          commentsHint:
            "Without secure boot: openstack flavor create vcf-flavor --ram 128 --disk 500 --swap 0 --vcpus 24 --private --property architecture='bare_metal' --property resources:CUSTOM_DISCOVERED='1' --property resources:DISK_GB='0' --property resources:MEMORY_MB='0' --property resources:VCPU='0' --property trait:CUSTOM_VCF='required'",
        },
        {
          id: "vcf-mgmt-vcf-deployer-url",
          questionPrimary: "vcf_deployer_url",
          questionSecondary:
            "URL to download vcf_deployer from — must be reachable from the esxi bootstrap node.",
          mandatory: true,
          exampleValue:
            "http://172.27.2.1/vcf_deployer-all_in_one-9.0.1-24957456-v0.1.0.ova",
          commentsHint:
            "Example: http://reachable.endpoint/vcf_deployer-all_in_one-9.0.1-24957456-v0.1.0.ova",
        },
        {
          id: "vcf-mgmt-vcf-deployer-ip",
          questionPrimary: "vcf_deployer_ip",
          questionSecondary:
            "IP of the vcf deployer VM — an IP in the CloudStore subnet (in the CIDR of the CloudStore customer subnet, outside the DHCP allocation pool) so it is reachable from the CloudStore.",
          mandatory: true,
          exampleValue: "172.27.2.1",
        },
      ],
    },
    {
      id: "vcf-mgmt-secrets",
      title: "Domaine de management — Mots de passe & secrets",
      rows: [
        {
          id: "vcf-mgmt-master-password",
          questionPrimary: "vcf_master_password",
          questionSecondary: "VCF Master password.",
          mandatory: false,
          exampleValue: "MYCOMPANYMa2026!",
          commentsHint:
            "Must contain only letters, numbers and at least 1 special character from @!#$%?^ and no other. Generated by the plan when left empty.",
        },
        {
          id: "vcf-mgmt-esxi-root-password",
          questionPrimary: "esxi_root_password",
          questionSecondary: "Default esxi root password.",
          mandatory: false,
          exampleValue: "MYCOMPANYMa2026!",
          commentsHint: "Generated by the plan when left empty.",
        },
        {
          id: "vcf-mgmt-appliance-password",
          questionPrimary: "appliance_password",
          questionSecondary: "VCF deployer vm password.",
          mandatory: false,
          exampleValue: "MYCOMPANYMa2026!",
          commentsHint: "Generated by the plan when left empty.",
        },
        {
          id: "vcf-mgmt-appliance-xapikey",
          questionPrimary: "appliance_xapikey",
          questionSecondary: "VCF deployer vm xapi password.",
          mandatory: false,
          exampleValue: "MYCOMPANYMa2026!",
          commentsHint: "Generated by the plan when left empty.",
        },
      ],
    },
    {
      id: "vcf-mgmt-misc",
      title: "Domaine de management — Divers",
      rows: [
        {
          id: "vcf-mgmt-ntp-server",
          questionPrimary: "ntp_server",
          questionSecondary: "NTP Server for VCF.",
          mandatory: true,
          exampleValue: "172.28.123.123",
          commentsHint: "Example: 10.3.2.11",
        },
        {
          id: "vcf-mgmt-vcf-subdomain",
          questionPrimary: "vcf_subdomain",
          questionSecondary: "Subdomain for VCF — combined with the dns_zone.",
          mandatory: true,
          exampleValue: "vcf",
          commentsHint: "Example: vcf",
        },
        {
          id: "vcf-mgmt-esxi-setup-script",
          questionPrimary: "esxi_setup_script",
          questionSecondary:
            "Script to setup the esxi. Required if deploying on hardware not validated by Broadcom.",
          mandatory: false,
          commentsHint:
            "Required when deploying on hardware not validated by Broadcom. Example otherwise: true. For unvalidated hardware, a JSON vSAN HCL override script piped into /usr/lib/vmware/vsan/perfsvc/stress.json followed by a vsanmgmtd restart is used.",
        },
        {
          id: "vcf-mgmt-keycloak-clusterissuer",
          questionPrimary: "keycloak_clusterissuer",
          questionSecondary: "ClusterIssuer to use for Keycloak.",
          mandatory: true,
          exampleValue: "customer-issuer",
          commentsHint: "Example: customer-issuer",
        },
      ],
    },
    {
      id: "vcf-wld-general",
      title: "Domaine workload — Général",
      rows: [
        {
          id: "vcf-wld-workload-domain-num",
          questionPrimary: "workload_domain_num",
          questionSecondary:
            "Rank of the created workload-domain — should be between 1 and 23.",
          mandatory: true,
          exampleValue: "1",
          commentsHint: "Example: 1",
        },
        {
          id: "vcf-wld-node-uuids",
          questionPrimary: "node_uuids (workload)",
          questionSecondary:
            "Baremetal node uuids of this workload domain (JSON list as string). Minimum 3 nodes per workload domain.",
          mandatory: false,
          commentsHint:
            "Provided by the CloudStore from the node selection — not filled by hand; keep default, no customer input required.",
        },
      ],
    },
    {
      id: "vcf-wld-network",
      title: "Domaine workload — Réseau",
      rows: [
        {
          id: "vcf-wld-external-network-id",
          questionPrimary: "vcf_external_network_id",
          questionSecondary:
            "User network id for this workload domain — the dedicated external network carrying NSX north-south (Tier-0) uplinks and customer workload traffic. Bound to grp2 of each host, carried by WLD-cluster-vdsXX via a Q-in-Q tunnel. Must exist before deployment.",
          mandatory: true,
          exampleValue: "1f380d53-4d31-43e9-8051-69081f7232ba",
          commentsHint:
            "Can be dedicated to this workload domain or shared with other workload domains and OpenStack projects. Its port groups are the customer responsibility.",
        },
        {
          id: "vcf-wld-vmotion-network-id",
          questionPrimary: "vcf_vmotion_network_id",
          questionSecondary:
            "vMotion network id — a network used for vMotion connectivity inside its own vlan.",
          mandatory: true,
          exampleValue: "f30c3c07-820b-4242-b9d4-20444bf407bb",
        },
        {
          id: "vcf-wld-vmotion-subnet-id",
          questionPrimary: "vcf_vmotion_subnet_id",
          questionSecondary: "vMotion subnet id — a subnet with a /24.",
          mandatory: true,
        },
        {
          id: "vcf-wld-vmotion-subnet-range",
          questionPrimary: "vmotion_subnet_range",
          questionSecondary: "The /24 range defined on the vMotion subnet.",
          mandatory: true,
          exampleValue: "172.18.8.0/24",
          commentsHint: "Example: 10.105.47.0/24",
        },
        {
          id: "vcf-wld-vmotion-vlan-id",
          questionPrimary: "vmotion_vlan_id",
          questionSecondary:
            "VLAN to isolate vMotion traffic — must match the VLAN set on vmotion_network.",
          mandatory: true,
          exampleValue: "806",
          commentsHint: "Example: 2047",
        },
        {
          id: "vcf-wld-vsan-network-id",
          questionPrimary: "vcf_vsan_network_id",
          questionSecondary:
            "vSAN network id — a network used for vSAN connectivity inside its own vlan.",
          mandatory: true,
          exampleValue: "6b6622c4-86bc-4047-9757-9a06f91caef6",
        },
        {
          id: "vcf-wld-vsan-subnet-id",
          questionPrimary: "vcf_vsan_subnet_id",
          questionSecondary: "vSAN subnet id — a subnet with a /24.",
          mandatory: true,
        },
        {
          id: "vcf-wld-vsan-subnet-range",
          questionPrimary: "vsan_subnet_range",
          questionSecondary: "The /24 range defined on the vSAN subnet.",
          mandatory: true,
          exampleValue: "172.18.6.0/24",
          commentsHint: "Example: 10.105.48.0/24",
        },
        {
          id: "vcf-wld-vsan-vlan-id",
          questionPrimary: "vsan_vlan_id",
          questionSecondary:
            "VLAN to isolate vSAN traffic — must match the VLAN set on vsan_network.",
          mandatory: true,
          exampleValue: "807",
        },
        {
          id: "vcf-wld-overlay-network-id",
          questionPrimary: "vcf_overlay_network_id",
          questionSecondary:
            "overlay network id — a network used for overlay connectivity inside its own vlan.",
          mandatory: true,
          exampleValue: "6b6622c4-86bc-4047-9757-9a06f91caef6",
        },
        {
          id: "vcf-wld-overlay-subnet-id",
          questionPrimary: "vcf_overlay_subnet_id",
          questionSecondary: "overlay subnet id.",
          mandatory: true,
        },
        {
          id: "vcf-wld-overlay-subnet-range",
          questionPrimary: "overlay_subnet_range",
          questionSecondary: "The /24 range defined on the overlay subnet.",
          mandatory: true,
          exampleValue: "172.18.7.0/24",
          commentsHint: "Example: 10.105.49.0/24",
        },
        {
          id: "vcf-wld-overlay-vlan-id",
          questionPrimary: "overlay_vlan_id",
          questionSecondary:
            "VLAN to isolate overlay traffic — must match the VLAN set on overlay_network.",
          mandatory: true,
          exampleValue: "805",
          commentsHint: "Example: 2049",
        },
      ],
    },
  ],
};

// ===========================================================================
// Context-archetype config (ContextConfig)
// ===========================================================================
// OPCP Context tab — a labeled key/value information form grouped into
// sections and nested subsections (Contacts). Slug `opcp-context`, title
// `OPCP Context`. Seeds come directly from the design data table. Row ids are
// stable and unique page-wide (they are the persistence rowIds, keyed by
// (installationId, slug, rowId)). `defaultValue` is required on every row;
// `''` models an empty default.
export const opcpContextConfig: ContextConfig = {
  sections: [
    {
      id: "ctx-client-environnement",
      title: "Client Environnement",
      rows: [
        {
          id: "ctx-env-client-name",
          label: "Nom du client",
          defaultValue: "MYCOMPANY COUNTRY",
        },
        {
          id: "ctx-env-deployment-type",
          label: "Type de deploiement",
          defaultValue: "NanoPod",
        },
        {
          id: "ctx-env-site1-location",
          label: "Site 1 Location",
          defaultValue: "« Demo » MYCOMPANY Rabat",
        },
        {
          id: "ctx-env-site2-location",
          label: "Site 2 Location",
          defaultValue: "",
        },
        {
          id: "ctx-env-install-wish-date",
          label: "Installation wish date",
          defaultValue: "",
        },
        {
          id: "ctx-env-managed-airgapped",
          label: "Managed / Air-gapped",
          defaultValue: "Managed",
        },
      ],
    },
    {
      id: "ctx-contacts",
      title: "Contacts",
      subsections: [
        {
          id: "ctx-contact-ovh",
          title: "OVH PSMC Architecte",
          rows: [
            {
              id: "ctx-contact-ovh-name",
              label: "Nom",
              defaultValue: "Samuel LEPETRE",
            },
            {
              id: "ctx-contact-ovh-phone",
              label: "Téléphone",
              defaultValue: "",
            },
            {
              id: "ctx-contact-ovh-email",
              label: "Email",
              defaultValue: "samuel.lepetre@ovhcloud.com",
            },
          ],
        },
        {
          id: "ctx-contact-client",
          title: "Client :",
          rows: [
            { id: "ctx-contact-client-name", label: "Nom", defaultValue: "" },
            {
              id: "ctx-contact-client-phone",
              label: "Téléphone",
              defaultValue: "",
            },
            {
              id: "ctx-contact-client-email",
              label: "Email",
              defaultValue: "",
            },
          ],
        },
      ],
    },
    {
      id: "ctx-use-cases",
      title: "Use cases (?)",
      rows: [
        {
          id: "ctx-usecase-cloudstore",
          label: "CloudStore",
          defaultValue: "Yes",
          inputType: "yesno",
        },
        {
          id: "ctx-usecase-vcf",
          label: "VCF",
          defaultValue: "Yes",
          inputType: "yesno",
        },
        {
          id: "ctx-usecase-suse-harvester",
          label: "SUSE Harvester",
          defaultValue: "No",
          inputType: "yesno",
        },
        {
          id: "ctx-usecase-nutanix",
          label: "Nutanix",
          defaultValue: "No",
          inputType: "yesno",
        },
        {
          id: "ctx-usecase-ia",
          label: "IA",
          defaultValue: "No",
          inputType: "yesno",
        },
        {
          id: "ctx-usecase-kubernetes",
          label: "Kubernetes",
          defaultValue: "No",
          inputType: "yesno",
        },
      ],
    },
  ],
};
