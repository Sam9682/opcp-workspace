# iFrames vs Native Integration for 'Core Apps' in Landing Zone Manager

> **🧭 VISION — Product idea (Product Management), NOT implementation status.** Mirror of the Confluence page [pageId 935461332](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=935461332) (v10, last modified 2026-05-25; mirrored 2026-06-10). Source = Confluence; on drift, Confluence wins. Use: planning/doc context for projects + runbooks.

---

This page is work-in-progress

**

  * Context
    * What are "Core Apps"?
    * What is postMessage
  * Comparison
    * Option A: iFrame Integration
      * Overview
      * postMessage limitations
        * Security Vulnerabilities
        * Performance Overheads
        * Implementation Limitations
    * Option B: Native Integration
    * Recommendation
  * Open Questions
  * Meeting notes
    * 2026-04-28



**

## Context

The Landing Zone Manager will aggregate multiple (existing) products (OVH products (KMS, MKS, etc.), SNC products (servers, block storage, etc.) and 'new ones', such as Observability) into a single user-facing platform. The most of these products are already built and maintained independently which brings us to the question: **How to integrate them into the Landing Zone Manager?** – by embedding them via iFrames, or by rebuilding the relevant UI natively within the Landing Zone Manager.

This decision affects every 'Core App' and will have long-term implications on UX, architecture and product evolution.

**The concern is: will use iframes induce design constraints and limitations ?**

### What are "Core Apps"?

"Core Apps" is not yet an official product term. For the purpose of this document, it refers to the set of services that are included in the **CloudStore licence as a non-splittable feature set, and which are providing enabler services** : **VM · Block Storage · Object Storage · Load Balancer · K8S · KMS · IAM · Observability**

These services are interdependent by design – for example, KMS requires K8S. They cannot be licensed or delivered individually, which makes them a natural candidate for deep, native integration into the Landing Zone Manager rather than being treated as interchangeable Cloud Store apps.

→ This is distinct from **Third Party Apps** , which are independent services not developed by OVHCloud and added via the Cloud Store and are out of scope for this document.

> A note on **Third Party Apps** Native integration provides consistency across Core Apps – but this promise has natural limits. Third Party Apps added via the Cloud Store will not follow the same design system or interaction patterns, regardless of whether Core Apps are built natively or via iFrame. This is an inherent challenge of an open marketplace model and should be addressed separately, e.g. through integration guidelines or a defined embedding standard for Third Party Apps.

### What is postMessage

Dealing with iframes implies using an API for parent/child frame communication; this is usually achieved with the postMessage HTML API

## Comparison

### Option A: iFrame Integration

#### Overview

Embed the existing internal products directly into the Landing Zone Manager via iFrames.

Dimension| Assessment  
---|---  
**Speed to market**|  ✅ Fast – existing UIs are reused as-is  
**UX Consistency**|  ❌ Each product has its own design language, navigation and interaction patterns – the Landing Zone Manager feels like a collection of separate tools rather than one cohesive product  
**Theming & Branding**| ❌ Hard to unify – iFrames are isolated, making consistent branding difficult  
**Onboarding & Learnability**| ❌ Different interaction patterns per app increase cognitive load for the user  
**Error Handling**|  ❌ No control over how errors are displayed – each app handles them differently, leading to an inconsistent and confusing experience  
**Navigation & Deep Linking**| ❌ Browser navigation (back button, URLs, deep links) becomes unreliable inside iFrames  
**Responsive / Mobile → Topic?**|  ❌ iFrames are notoriously difficult to make responsive  
**Observability Integration**|  ❌ No context on object-level events inside the iFrame (e.g. „enable logging for this bucket?" not possible)  
**Project Scoping**|  ❌ Risk that users see resources outside their project scope if not carefully controlled  
**Authentication**|  ❓ Is token handling across iFrame boundaries a security concern that needs to be addressed?  
**Security**|  ❓ Are there cross-origin or clickjacking risks that need to be evaluated?  
**Future Rewrite**|  ❓ Does an iFrame-based approach create technical debt that complicates a future rewrite?  
**Maintenance**|  ❓ How are UI changes in source products managed across iFrame boundaries?  
  
#### postMessage limitations

While `postMessage` is the gold standard for cross-origin communication, it isn’t a magic wand. It comes with specific architectural hurdles and security risks that can bite you if you aren't careful.

* * *

##### Security Vulnerabilities

Because `postMessage` bypasses the **Same-Origin Policy** , it opens up new attack vectors.

  * **Origin Spoofing:** If you don't explicitly check `event.origin`, any site can send a message to your listener. A malicious site could send a command like `{ "action": "delete_user" }`, and if your code doesn't verify who sent it, it will execute.

  * **Data Leakage:** If you use the wildcard `*` as the target origin when sending data, **any** window can listen in and intercept that information.

  * **XSS Risks:** If you take the data from a message and inject it directly into the DOM (e.g., using `.innerHTML`), you are creating a **Cross-Site Scripting** vulnerability.




* * *

##### Performance Overheads

`postMessage` is not a "shared memory" system; it’s a **message-passing** system.

  * **Serialization Cost:** When you send an object, the browser performs a **Structured Clone**. It has to serialize the data on one side and deserialize it on the other. For massive datasets or high-frequency updates (like 60fps game coordinates), this can cause noticeable "jank" or UI lag.

  * **Asynchronous Nature:** The communication is strictly asynchronous. You cannot "return" a value from a `postMessage` call. You have to send a message, set up a listener on the original side, and wait for a "response" message to come back.




* * *

##### Implementation Limitations

There are certain things you simply cannot send or do with `postMessage`.

  * **Unsupported Types:** You cannot send objects with methods (functions), DOM elements, or certain complex prototypes. Only data that can be cloned (Strings, Numbers, Arrays, Plain Objects, Blobs, etc.) is allowed.

  * **Race Conditions:** If the iframe hasn't finished loading yet, `postMessage` calls sent by the parent will simply vanish into the void. You often have to implement a "handshake" protocol where the iframe tells the parent, "I'm ready!" before communication starts.

  * **Debugging Difficulty:** Unlike direct function calls, tracking the flow of `postMessage` can be a headache. It doesn't show up clearly in standard stack traces, making it harder to debug "where this event came from" in complex applications.




  


* * *

### Option B: Native Integration

Rebuild the relevant UI components natively within the Landing Zone Manager, aligned to a shared design system and UX standard.

  


Dimension| Assessment  
---|---  
**Speed to market**|  ❌ Slower – requires rebuilding existing UIs  
**UX Consistency**|  ✅ Full control – unified design language, navigation and interaction patterns across all Core Apps  
**Theming & Branding**| ✅ Consistent branding across all Core Apps  
**Onboarding & Learnability**| ✅ Users learn one system – patterns are predictable and transferable across Core apps  
**Error Handling**|  ✅ Unified error handling and messaging that fits the platform's tone and design  
**Navigation & Deep Linking**| ✅ Full control over browser navigation, URLs and deep linking  
**Responsive / Mobile → Topic?**|  ✅ Full control over responsive behavior →   
**Observability Integration**|  ✅ Object-level observability opt-in possible (e.g. per bucket, per VM)  
**Project Scoping**|  ✅ Per-project data scoping enforced natively and consistently  
**Authentication**|  ❓ Does native integration simplify auth handling compared to iFrames?  
**Security**|  ❓ Does native integration eliminate the cross-origin risks associated with iFrames?  
**Future Rewrite**|  ❓ Does building natively now reduce the effort of a future rewrite?  
**Maintenance**|  ❓ How are API changes in source products communicated to the LZPlattform team?  
  
* * *

### Recommendation

  
| iFrame| Native  
---|---|---  
**Short-term effort**|  Low| High  
**Long-term effort**|  High| Low  
**UX outcome**|  Fragmented| Cohesive  
**Observability**|  Not possible at object-level| Fully supported  
**Strategic fit**|  ❌| ✅  
  
  


Native integration requires more upfront investment but is the only approach that delivers a coherent user experience, supports the platform's observability model, and avoids structural technical debt. The iFrame approach may appear faster now, but effectively defers the problem and adds complexity to any future rewrite.

  


* * *

## Open Questions

  * we could also define the Core Apps as apps that depend heavily on OPCP Core (VM, Block, LB) – S3 may not be one
  * what are the objections that are really relevant for the Core Apps ?



  


## Meeting notes

### 2026-04-28

Carsten, Florent, Leena, Maxime

Summary: iframes are not a limiting factor in terms of UX, and Leena should not consider this to be a differenciating factor when designing experiences. We will see in a few days/weeks if the iframe-based packaging of the SNC Cloud Platform Control Panel does deliver the same UX as the monolithic one.

  

