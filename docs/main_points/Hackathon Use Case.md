### **Hackathon Use Case: Give our AI Supply Chain Manager ‘Agnes’ Raw Material Superpowers**

CPG companies regularly overpay because sourcing is fragmented. The same ingredient may be purchased by multiple companies, plants, or product lines without anyone having full visibility into the combined demand. That means suppliers do not see the true buying volume, orders are not consolidated, and buyers lose leverage on price, lead time, and service levels. But consolidation is only valuable if the components are actually substitutable and still compliant in the context of the end product.

This is where AI creates value: it can connect fragmented purchasing data, infer which materials are functionally equivalent, verify whether quality and compliance requirements are still met, and recommend sourcing decisions that are cheaper, more scalable, and operationally realistic.

At **Spherecast**, we think of this capability as **Agnes**: an AI Supply Chain Manager that helps teams make better sourcing decisions by reasoning across fragmented supply chain data. This hackathon invites participants to challenge our current approach and push that vision further.

In this hackathon challenge, students are invited to design and build an **AI-powered decision-support system** for sourcing in the CPG **industry.** Teams will work on a realistic problem faced by a company that centrally manages procurement intelligence and uses it to support customers in the CPG space.

Given multiple normalized **bill of materials (BOMs)**, existing supplier relationships, and historical procurement decisions across several companies[[1]](#_msocom_1) , teams must determine which components are genuinely substitutable and which sourcing decisions can be consolidated. The scope includes only **raw ingredients**.

The challenge goes far beyond simple cost optimization. Teams must infer whether a cheaper or more consolidated alternative still satisfies the **quality and compliance requirements** of the finished product. This may require combining structured internal data with incomplete external evidence such as **supplier websites, product listings, certification databases, label images, packaging text, public product pages, and regulatory references**. A sourcing recommendation is only valid if the system can justify that **compliance and quality constraints are still met**.

The focus lies on making incomplete and messy data actionable: identifying functional substitutes, inferring compliance-relevant requirements, and producing an **explainable sourcing proposal** that balances **supplier consolidation, lead time, and practical feasibility**. There is no single correct answer. This is an intentionally **open-ended challenge** centered on reasoning quality, trustworthiness, and business value.

**Target Group**

●      Students interested in applying AI, data sourcing, and optimization

●      Students with knowledge of **LLMs, retrieval systems, agentic workflows, multimodal methods, optimization, data sourcing, scraping**

●      Teams that enjoy solving open-ended, real-world problems with incomplete information

**Core Challenge**

●      Identify **functionally interchangeable components** at the component level, including ingredients

●      Infer which **quality and compliance requirements** a substitute must satisfy, based on structured data and external evidence

●      Produce an **explainable sourcing recommendation** with evidence trails and tradeoff explanations across supplier consolidation and compliance

**The Application to Be Built**

●      An **internal AI decision-support application** for cons-industry sourcing

●      A system that ingests organizer-provided **BOM and supplier data** and enriches it with **external information**

●      A solution that proposes likely substitute components and evaluates whether they are acceptable in the context of the end product

●      A reasoning layer that surfaces **sources, evidence trails, and tradeoff explanations**

●      An optimization or recommendation layer that produces a **consolidated sourcing proposal** per component category or product group

**Data Provided**

●      Normalized **BOM data**

●      Supplier data, including existing supplier-to-component mappings

●      An **SQL database dump** and explaining ERD

**Technology Setup**

●      The challenge is **technologically agnostic**

●      Teams may use any models, frameworks, orchestration patterns, multimodal approaches, or hosting stack

●      External enrichment is strongly encouraged and will be necessary for strong results

●      Participants are expected to decide for themselves how to **retrieve, verify, structure, and operationalize and reconstruct missing evidence**

**Deliverables**

●      A **working prototype** or technical decision-support system

●      A presentation including:

○      Problem framing and business relevance

○      Data acquisition and enrichment strategy

○      Approach to substitution detection and compliance inference

○      Optimization / recommendation logic

○      Architectural decisions and model choices

○      Demonstration of the system

●      A clear explanation of how the system handles **uncertainty, evidence quality, and tradeoffs**

**Judging Emphasis**

●      Practical usefulness and business relevance

●      Quality of reasoning and evidence trails

●      Trustworthiness and hallucination control

●      Ability to source and operationalize missing external information

●      Soundness of the substitution logic and compliance inference

●      Quality and defensibility of the final sourcing proposal

●      Creativity in showing how the system could scale and improve over time

●      **UI polish is not a priority**

---

 [[1]](#_msoanchor_1)This is not provided in the data in this challenge; but could be used in the future from customers.