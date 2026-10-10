# Performance Requirements & Sizing

> **🧭 VISION — Product idea (Product Management), NOT implementation status.** Mirror of the Confluence page [pageId 888447115](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=888447115) (v2, last modified 2026-03-03; mirrored 2026-06-10). Source = Confluence; on drift, Confluence wins. Use: planning/doc context for projects + runbooks.

---

### Performance Requirements & Sizing

**Overview & Scale Target**

The OPCP Core observability stack can be standardized on the LGTM stack (Loki, Grafana, Tempo, Mimir) as we now have the approval to use AGPLv3-licensed software inside OPCP. 

Officially, the largest OPCP model must scale up to 100 racks of 44U. This requires the observability stack to support a maximum of 4,400 physical machines, alongside VM probing and network switches.

  


_High-Level Note: A Prometheus scraped instance does not equal a single physical node. A single physical machine runs multiple services, containers, and exporters. Therefore, 4,400 physical nodes will result in significantly more than 4,400 scraped instances._

**The Key Scaling Metric: Active Series Per Node**

In Mimir, the primary bottleneck is Ingester CPU and RAM, which is dictated almost entirely by the number of active series held in memory, not by the retention duration. To accurately size the OPCP Core controllers, we should determine the true **Active Series per Node**.

**Baseline Reality Check (The Conservative Assumption based on gridscale control plane with high actve series per node)**

Initial capacity planning ran a self-developed cardinality script against the `gridscale gs-prod` environment (1,359 instances generating ~6.1 million series, requiring ~87 CPU cores). Extrapolating this linearly to 4,400 nodes suggests the current 3-node HA controllers (48 cores total) can only support ~2 racks before severe CPU starvation and dropped data occur.

However, this assumption is highly conservative.

  * `gs-prod` is a dense ops-center stack generating ~4,500 series per instance.
  * Standard bare-metal compute nodes are assumed to be much lighter.
  * The true controller sizing depends on which of the following scenarios applies to the data plane:



#### Scenario A: Sparse Compute Nodes (No VM Probing on Tier 1)

  * **Assumption:** Standard bare-metal nodes running basic exporters (`node_exporter`, `promtail`) generate **500 to 1,000 active series per node**.

  * **Global Cardinality:** 4,400 nodes × 1,000 series = ~4.4 Million active series.

  * **Impact:** With Mimir 3.0 engine efficiencies, aggressive label dropping (e.g., stripping high-churn labels like `alloc_id` or `session_id`), and reducing the replication factor to 2, this workload _might_ fit a 3-controller cluster, requiring a hardware bump of the 3 controllers




#### Scenario B: Dense Compute Nodes (Full VM Probing via OpenStack)

  * **Assumption:** Compute nodes expose hypervisor-level metrics for their hosted VMs (e.g., via `libvirt`). If a node hosts 50-100 VMs, generating 150-250 series per VM, the cardinality skyrockets to **~20,000 active series per node**.

  * **Global Cardinality:** 4,400 nodes × 20,000 series = ~88 Million active series.

  * **Impact:** Mimir would require roughly **300 CPU cores** just for ingestion. The current 48-core controller setup will instantly fail due to CPU starvation.




#### Architectural Options to Support 4,400 Nodes

If Scenario B (Dense Nodes) is required, we must adopt one of two architectural paths:

  1. **Option 1: Massive Controller Scaling**

Abandon the current 3x 16-core HA controller setup. Scale out the OPCP Core controllers to **5 to 7 massive nodes** , each equipped with **96+ CPU cores and 1TB+ of RAM**.

     * _Trade-off:_ This significantly increases the fixed cost of the OPCP Core, which is included in the OPCP price and not directly billed to the customer.

  2. **Option 2: Two-Tiered Push Architecture (Edge Filtering)**

Restrict the OPCP Core controllers (Tier 1) to a "Micro" stack that _only_ ingests L1/L2 hypervisor aggregates (keeping it in Scenario A limits).

     * Deploy Edge Agents (OTEL collector) on all nodes to push telemetry.

     * Strip high-cardinality labels and strictly filter out per-VM (L3) metrics at the edge → high risk, as we need very good planning + high discipline

     * Route all heavy L3 data (per-VM metrics, application logs) directly to a scalable **Tier 2 Customer Stack** (packaged as a Cloud App and billed to the customer).

  3. Option 3: Use data plane nodes for the core observability stack



Reserve OPCP nodes in the data plane for the observability stack, e.g. 1 node pr 1-2 racks. This would offload scaled costs to the customers → similar approach as with block storage.

#### Next Steps / TODOs:

  * **TODO:** Run the cardinality script against the currently productive SNC and BMPod compute nodes to measure the _exact_ **Active Series per Node**. This will immediately tell us if we are in Scenario A or Scenario B.

  * **TODO:** Decide internally if OPCP Core must ingest per-VM metrics natively, or if that can be offloaded to the Customer Tier → I think at least VM probing is needed.

  * **TODO:** Talk to OVH observability experts running large-scale Mimir and Loki instances at scale and let exactly these assumptions be challenged.



  

