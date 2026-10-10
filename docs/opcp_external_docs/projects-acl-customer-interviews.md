# Projects / ACL customer interviews

> **🧭 VISION — Product idea (Product Management), NOT implementation status.** Mirror of the Confluence page [pageId 942457731](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=942457731) (v9, last modified 2026-05-12; mirrored 2026-06-10). Source = Confluence; on drift, Confluence wins. Use: planning/doc context for projects + runbooks.

---

  * Questions
  * Deep
  * Michelin
  * Netic
  * CND



## Questions

  * How common is the case where a user needs access to a specific project only in one region (e.g. projectA in Paris only, but projectC everywhere)?
  * do you foresee a need to grant access to a specific service within a project — e.g. a user can use VM in Project X but not S3 in the same project?
  * how do they materialize RBAC company-wide (in LDAP ?); what are best practices for revokation and auditability
  * what's their practice on groups-based permission vs user-based permission
  * how do they isolate per project today



## Deep

Profile: DIY Cloud Provider

  * no need for cross region projects (usecase for them: customer-dedicated OPCP)
  * by default only the tenant admin should be allowed to create projects and assign groups to it, but it should be possible to grant a "can create projects" permission to specific user groups / users / or even everyone
  * the more finegrained control the better (action scoping, resource scoping, service scoping) but it's not needed in v0; however the model should allow for a gradual addition of fine control
  * they usually manage RBAC in LDAP, with the following structure: user > org group (eg, "Devops Engineers") > Functional group ("e.g, OPCP-Project1-Admin", "OPCP-Project2-Reader") and expect (best practice) to be able to grant a role on a project to a group; they mentioned recursive application ("Devops Engineers" members should get access to all Functional groups below) but i think it's not needed (they should just grant the group "Devops Engineers" the permission on each project)
  * they have a team-first vision, not individual users (cf on-call duty, etc…)
  * having the structure in LDAP allows for a 360 view audit on who accesses what for the whole company
  * the local management model is still useful, as it will allow smaller customers or POCs to start without the LDAP/AD/SSO link, but it should be blocked if the org sync is present



## Michelin

Profile: private corporate datacenter

  * no need for cross region projects, projects are location-defined (multi-region usecase for them: factories); anyone who needs the same project name across regions should just create it with the same name
  * no need for service scoping inside one project, as admins are usually responsible for an entire region (i.e the local admin guy)
  * today they use VCF, no project scoping at all exists (someone with access has access to everything) – seems to work with the factory model where the local IT guy is on call, and they isolate on the network layer with NSX
  * permissions should be done with groups, not users, otherwise account reviews are required which is very costly; groups should map to job title more than location (e.g, devops are devops on all regions; when they become managers they should lose their permission)
  * today they have custom tools (forms, UIs) which provision the required LDAP structures and use an Identity Governance & Administration tool to have workflows which ensure that newcomers, movers and quitters are getting auditable, management-validated and updated permissions; in some cases the RBAC is reflected in LDAP/AD (ex: app-users, app-admins) and this is the best practice
  * they have one SSO for the entire company (SAML/OIDC capable)
  * group definition should be readonly when synced from LDAP/AD
  * manual user accounts should be created for service/system accounts (i.e for machines); they are usually readonly (eg AI)
  * the michelin vision is towards self service: anyone with an account should be able to create projects, but with quotas
  * per-project service activation is mandatory (by the tenant admin), so that they roll out new services progressively
  * fine-grained action scoping could be useful at some point (e.g, no destructive actions) – think of AI



## Netic

Profile: DIY Cloud Provider

  * their billing structure:
    * customer
      * project
        * subscription (cross-region) = resource
  * K8S
    * roles
      * single namespace: ro, dev
      * multiple namespaces: superuser
      * all namespaces: cluster admin
      * all clusters: tenant admin
    * they do not support group-based roles (only individuals)
  * cross-region projects are increasing in demand, but it's not a common practice amongh their customers
    * could prevent namespacing problems for consolidated billing
    * but in case of cross cloud provider the problem exists anyway
    * never had the request of having a user only allowed to manage one region for a cross-region project
  * LDAP
    * most of their customers have it but few configure an integration, usually rely on local accounts
  * restricting service access to some users inside a project is not a usecase for them (someone who can manage the project has access to all services with the same role)
  * projects and VPC could be related (i.e a cross-region project could automatically enable cross-region connectivity) ?
  * group-based authentication is the future / best practice but individual is still needed for small projects
  * would prefer an explicit onboarding/offboarding process (with identify verification) rather than a dynamic user provisioning



## CND
