# Resource Hierarchy Market Status

> **🧭 VISION — Product idea (Product Management), NOT implementation status.** Mirror of the Confluence page [pageId 942138401](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=942138401) (v3, last modified 2026-05-13; mirrored 2026-06-10). Source = Confluence; on drift, Confluence wins. Use: planning/doc context for projects + runbooks.

---

## GCP

GCP is project-centric, and follow this structure Organization > Folder > Project > Resource ; resources can be global or regionalized. Users have roles on resources. A user can belong to many project, and each project has it's own IAM policy inherited from parent folders/org.

<https://docs.cloud.google.com/resource-manager/docs/cloud-platform-resource-hierarchy>

<https://docs.cloud.google.com/resource-manager/docs/creating-managing-projects>

<https://docs.cloud.google.com/compute/docs/regions-zones>

## AWS

Unlike Azure or GCP, AWS IAM doesn't organize permissions hierarchically. Instead, each user, group, or role gets policies attached directly. This means you must explicitly manage permissions for every entity, which can get complex in large organizations, but allows very detailed access specifications.

Everything is regionalized, except for global resources like IAM.

The multi-account structure is handled by AWS Organizations: accounts can be organized in a hierarchical tree of Organizational Units (OUs) nested under a root. When you attach a policy (SCP) to a node, it flows down and affects all branches and leaves beneath it. Each account can be a member of exactly one OU.

User access is managed at the account level and can't be managed at the Organization or OU level — this disadvantage can be overcome by using SSO authentication with the AWS IAM Identity Center.

The "project" concept maps to an AWS **Account** , not a resource inside a single account. Users are assigned roles they _assume_ , rather than being directly bound to resources.

## Azure

Azure's organization is based on Management Groups and Subscriptions. Management groups are logical containers that enable administrators to simultaneously manage access, policy, and compliance for multiple subscriptions. All subscriptions within a management group automatically inherit the conditions applied to it.

Policies are scoped at four hierarchical levels: Management Group, Subscription, Resource Group, and Resource. Generally, each level up is a broader access definition.

Azure excels in adaptive access control. Conditional Access enables context-aware policies (location, device, risk score), while Privileged Identity Management (PIM) allows just-in-time access with approval workflows and audit logging for sensitive roles.

Azure assumes a single org/tenant (rooted in Azure AD/Entra ID). Users are first-class AD objects; their relationship to projects (subscriptions/resource groups) is expressed via RBAC role assignments at a given scope.

## OVHCloud

Structure: Account → Resources (no "Project" as a primary unit)

OVHcloud's organizing concept is the **Account** (a customer account ID, e.g. `xx1111-ovh`), not a "project." A resource is an OVHcloud product impacted by a policy — a domain name, a Nutanix server, a Load Balancer, etc. Resources don't live inside a project container; they are identified individually by a **URN** and attached directly to an account.

To manage many resources together, OVHcloud offers **Resource Groups** : it is possible to set up a resource group that aggregates several resources under a unique URN, to ease policy management for a large number of resources. This is a flat grouping mechanism, not a hierarchy.

The Public Cloud product line does have a "Project" concept (inherited from OpenStack), but it's a _product_ , not a governance layer — it's essentially one resource among many, not a container that structures IAM.

There are four identity types on an OVHcloud account: **local users** (human, login/password, for console access), **service accounts** (machine identities, client/token-based, for programmatic access), **federated users** (from a third-party SSO directory, represented by user groups in rights management), and the **account itself** (the root owner identity).

OVHcloud's policy model is the most **resource-centric** of any cloud reviewed here. A policy consists of identities (account, user, or group URNs), resources (specific product URNs or resource group URNs), and permissions — with an `allow` array, a `deny` array, and an `except` array for fine-grained exclusions.

Actions belong to five categories: Create, Delete, Edit, Operate, and Read.

Notably, policies can also target other OVHcloud customer accounts. The targeted account will be able to manage the rights received that way on its own policies, but will never be able to override the rights set on the access policy. This is a delegation model somewhat similar to AWS cross-account roles.

OVHcloud **skips the project abstraction entirely** and goes straight to resource-level IAM. This gives maximum granularity but creates real operational burden — you're attaching policies to individual resource URNs rather than to a logical container.

<https://www.ovhcloud.com/en/identity-security-operations/identity-access-management/>

## Scaleway

Scaleway follows a 2 level structure: Organization → Project.

A **Project is a grouping of Scaleway resources**. **Each Organization comes with a default Project** , and you can create new ones. **Projects are cross-region** , meaning resources in different regions can be grouped in a single Project. You can use IAM to define custom access rights per Project. Projects are cross-region.

There is no intermediate layer (no Folder, no OU, no Management Group) — it's a flat Organization → Projects hierarchy. Simpler than GCP or Azure, but less flexible for large orgs.

A rule is the part of a policy that defines the permissions of its principal, and the scope of those permissions. It consists of a scope (at Project level or Organization level) and one or more permission sets. A policy can have one or many rules. Rules can only grant access — you cannot create a rule that explicitly denies access to specific actions/resources.

A scope can be at Project or Organization level. Billing, IAM, Project management and support are managed at Organization level. If you choose Project-level scope, you can select one, many, or all Projects.

**Access management at resource level is not yet available** — you can currently only scope permission sets to a Project or to an Organization. Explicit deny permissions are not yet available; you can currently only explicitly allow access.

#### Oxide

<https://docs.oxide.computer/guides/operator/silo-management>

Hierarchy:

  * Fleet
    * Silo
      * Project



Roles:

  * admin
  * collaborator
  * limited_collaborator
  * viewer



Supported IDPs:

  * SAML + JIT provisioning
  * SAML + SCIM 2.0



## Comparison

![](https://confluence.ovhcloud.tools/download/attachments/embedded-page/CPO/Resource%20Hierarchy%20Market%20Status/image-2026-5-13_18-3-36.png?api=v2)
