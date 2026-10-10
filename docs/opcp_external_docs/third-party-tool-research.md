# Third party tool research

> **🧭 VISION — Product idea (Product Management), NOT implementation status.** Mirror of the Confluence page [pageId 878626016](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=878626016) (v1, last modified 2026-02-18; mirrored 2026-06-10). Source = Confluence; on drift, Confluence wins. Use: planning/doc context for projects + runbooks.

---

> Disclaimer: This is a mostly technical perspective on Lago and KillBill. Feature wise, these tools should be evaluated by the product teams as well, because, at least to me, it’s currently quite unclear which features we might need and which we might not need, so I can not give a qualified recommendation on these parts of lago and killbill. However, I will mention features I found noteworthy, either their existence or their lack of a feature.
> 
> Note as well, that the focus here is mainly on the ability to customize those tools, regardless of language choice.

  


Lago:

  * Written in go

  * <https://getlago.com/>
  * AGPLv3 license

  * Mainly intended as SaaS, however there are options to self-host and get enterprise level support
  * Customization

    * No plugin API

    * only extension point is Lago’s HTTP API

    * Alternatively, we could fork the project and work directly on Lago’s source code, however, we would need to open-source the current state of the fork at all times, as per the AGPLv3 license

  * Apparently no hierarchical accounts out of the box

  * Pretty complex architecture, consisting of multiple background worker processes

    * See <https://github.com/getlago/lago/blob/main/docs/architecture.md>




  


KillBill

  * Written in Java

  * <https://killbill.io/>
  * Apache License 2.0

  * Intended to be self-hosted from the get go
  * Headless system

  * Customization

    * OSGi compliant plugin API

    * Additionally, a comprehensive HTTP API

  * Hierarchical accounts supported out of the box

  * Includes an optional admin GUI




Conclusion:

From a purely technical perspective, KillBill seems like the better option, if a third-party tool should be chosen at all. With its plugin API, we would be much more flexible in customizing the system to our needs, than we would be with only an HTTP based API.

As hierarchical accounts are, to my understanding, required for OPCP/SNC billing, Lago should not be used, as it doesn’t provide this functionality out of the box and there’s no obvious way, how one would bring this functionality into Lago.

While KillBill does support hierarchical accounts, it doesn’t seem to support multiple levels of hierarchical accounts, restricting child accounts to never have child-accounts of their own. However, this could probably be implemented as a plugin, though, this would need further research.
