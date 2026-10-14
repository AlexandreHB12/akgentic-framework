"""Generate the hardware-support-team fake data and catalog bundle.

Every record lives once, in this file, and each agent's workspace files are
derived from it — so a client, SKU, price, contract discount or order quantity
is the same wherever it appears. Stock ``reserved`` is computed from the open
order lines, and every order's unit price from the list price and the contract
in force on the order date, so the stock, order, sales and contract views can
never drift apart.

Outputs:
    data/demo-data/hardware-support-team/<workspace>/...   the seeded files
    data/catalog-import/catalog.hardware-support-team.yaml  the import bundle

The bundle is ``catalog.template.yaml`` with each ``{{file:<workspace>/<name>}}``
marker replaced by that file's content as an indented block scalar.

Usage:
    uv run python scripts/build_hardware_support_team.py
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data/demo-data/hardware-support-team"
TEMPLATE = DATA_DIR / "catalog.template.yaml"
BUNDLE = ROOT / "data/catalog-import/catalog.hardware-support-team.yaml"

TODAY = date(2026, 10, 2)
COMPANY = "Voltaris Hardware"
WAREHOUSE = "Liège DC"

# ── Products ────────────────────────────────────────────────────────────────
# category drives the contract discount bucket: Datacenter / Networking / Endpoint
PRODUCTS = [
    dict(sku="VX-SRV-R250", name="Voltaris R250 1U Rack Server", category="Datacenter",
         list_price=4890.00, lifecycle="Active", warranty="3 years next-business-day onsite",
         summary="Single-socket 1U rack server for branch offices, virtualisation hosts and edge workloads.",
         specs="1x 16-core Xeon-class CPU (2.9 GHz); 128 GB DDR5 ECC (max 1 TB, 8 DIMM slots); "
               "4x 2.5\" hot-swap NVMe/SAS bays; 2x 10GbE SFP+ onboard; 1x PCIe 5.0 x16 slot; "
               "redundant 800 W PSUs; Voltaris BMC remote management; 1U, 16 kg.",
         compatible="VX-SSD-3840 (up to 4 drives), VX-SFP-10G-SR, VX-RACK-42U, VX-UPS-1500.",
         substitutes="VX-SRV-R450 when more cores, memory or drive bays are needed (2U, higher price).",
         cross_sell="VX-SSD-3840 drives, VX-SFP-10G-SR optics, VX-UPS-1500."),
    dict(sku="VX-SRV-R450", name="Voltaris R450 2U Rack Server", category="Datacenter",
         list_price=11250.00, lifecycle="Active", warranty="3 years next-business-day onsite",
         summary="Dual-socket 2U workhorse for databases, virtualisation clusters, research computing and GPU workloads.",
         specs="2x 24-core Xeon-class CPUs (2.6 GHz); 256 GB DDR5 ECC (max 4 TB, 32 DIMM slots); "
               "12x 3.5\"/2.5\" hot-swap bays (SAS/NVMe); 4x 10GbE SFP+ onboard; up to 2 double-width "
               "GPUs (300 W each); redundant 1400 W PSUs; Voltaris BMC; 2U, 28 kg.",
         compatible="VX-SSD-3840, VX-HDD-16T, VX-SFP-10G-SR, VX-RACK-42U, VX-UPS-1500 (one UPS per two servers).",
         substitutes="VX-SRV-R250 for lighter single-socket workloads (fewer bays, half the memory slots).",
         cross_sell="VX-RACK-42U and VX-UPS-1500 for new deployments; VX-NET-S48X for 10G cluster fabric."),
    dict(sku="VX-STO-N8", name="Voltaris N8 8-Bay NAS", category="Datacenter",
         list_price=2390.00, lifecycle="Active", warranty="3 years return-to-base",
         summary="Desktop/tower 8-bay NAS for file sharing, backup targets and small-office video storage.",
         specs="8x 3.5\" SATA/SAS bays (drives not included); quad-core CPU; 16 GB ECC (max 64 GB); "
               "2x 2.5GbE + 1x 10GbE RJ45; RAID 0/1/5/6/10; snapshots and replication; max raw capacity "
               "128 TB with VX-HDD-16T.",
         compatible="VX-HDD-16T (up to 8). Not compatible with VX-SSD-3840 (no U.2/NVMe bays).",
         substitutes="VX-STO-N16 when rack mounting, SFP+ or more than 8 drives is needed.",
         cross_sell="VX-HDD-16T drives (sold separately), VX-UPS-1500."),
    dict(sku="VX-STO-N16", name="Voltaris N16 16-Bay Rack NAS", category="Datacenter",
         list_price=6980.00, lifecycle="Active", warranty="3 years next-business-day onsite",
         summary="3U rack NAS for departmental storage, imaging archives (PACS), research data and backup.",
         specs="16x 3.5\" SAS bays + 2x U.2 NVMe cache bays (drives not included); 8-core CPU; 64 GB ECC "
               "(max 512 GB); 2x 10GbE SFP+ + 2x 1GbE; RAID 5/6/10/60; dual controllers optional; max raw "
               "capacity 256 TB with VX-HDD-16T; 3U, 31 kg.",
         compatible="VX-HDD-16T (up to 16), VX-SSD-3840 (only in the 2 U.2 cache bays), VX-SFP-10G-SR, "
                    "VX-RACK-42U, VX-UPS-1500.",
         substitutes="VX-STO-N8 for small sites (desktop, 8 bays, no SFP+).",
         cross_sell="VX-HDD-16T drives, 2x VX-SSD-3840 as read/write cache, VX-SFP-10G-SR optics."),
    dict(sku="VX-SSD-3840", name="Voltaris 3.84 TB Enterprise NVMe SSD", category="Datacenter",
         list_price=689.00, lifecycle="Active", warranty="5 years or 7 PBW, return-to-base",
         summary="U.2 NVMe data-centre SSD for server boot/data volumes and NAS caching.",
         specs="3.84 TB; U.2 (2.5\", 15 mm) PCIe 4.0 x4; 6,800 MB/s read / 4,000 MB/s write; 1 DWPD; "
               "power-loss protection; hot-swap tray included.",
         compatible="VX-SRV-R250, VX-SRV-R450, VX-STO-N16 (cache bays only). Not compatible with VX-STO-N8.",
         substitutes="None in the current range.",
         cross_sell="Sold with VX-SRV-R250 / VX-SRV-R450 configurations."),
    dict(sku="VX-HDD-16T", name="Voltaris 16 TB Enterprise SAS HDD", category="Datacenter",
         list_price=429.00, lifecycle="Active", warranty="5 years return-to-base",
         summary="7,200 rpm 3.5\" capacity drive for NAS and server bulk storage.",
         specs="16 TB; SAS 12 Gb/s (also works on SATA backplanes of VX-STO-N8); 7,200 rpm; 512 MB cache; "
               "550 TB/year workload rating; hot-swap tray included.",
         compatible="VX-STO-N8, VX-STO-N16, VX-SRV-R450.",
         substitutes="None in the current range.",
         cross_sell="Sold with VX-STO-N8 / VX-STO-N16 (NAS units ship without drives)."),
    dict(sku="VX-NET-S24", name="Voltaris S24 24-Port PoE+ Switch", category="Networking",
         list_price=1290.00, lifecycle="Active", warranty="Limited lifetime, next-business-day advance replacement",
         summary="Managed L2+ access switch that powers access points, cameras and phones.",
         specs="24x 1GbE PoE+ (370 W budget); 4x 10GbE SFP+ uplinks; L2+ static routing; VLAN, LACP, "
               "802.1X; cloud or local management; 1U, fanless below 200 W load.",
         compatible="VX-NET-AP6, VX-NET-AP7 (PoE+ powers one AP7 per port at full performance), "
                    "VX-SFP-10G-SR uplinks, VX-NET-FW200.",
         substitutes="None at 24 ports; for 10G aggregation use VX-NET-S48X.",
         cross_sell="VX-SFP-10G-SR uplink optics; pairs with VX-NET-AP7 rollouts."),
    dict(sku="VX-NET-S48X", name="Voltaris S48X 48-Port 10G Switch", category="Networking",
         list_price=7450.00, lifecycle="Active", warranty="Limited lifetime, next-business-day advance replacement",
         summary="L3 aggregation/top-of-rack switch for server and storage networks.",
         specs="48x 10GbE SFP+; 6x 100GbE QSFP28; full L3 (OSPF, BGP); VXLAN; redundant hot-swap PSUs "
               "and fans; 1U.",
         compatible="VX-SFP-10G-SR, VX-SRV-R250, VX-SRV-R450, VX-STO-N16, VX-NET-S24 uplinks.",
         substitutes="None in the current range.",
         cross_sell="VX-SFP-10G-SR optics (one per used port, both ends)."),
    dict(sku="VX-SFP-10G-SR", name="Voltaris 10G SFP+ SR Transceiver", category="Networking",
         list_price=59.00, lifecycle="Active", warranty="Limited lifetime",
         summary="10GBASE-SR multimode optic for links up to 300 m.",
         specs="SFP+, 850 nm, LC duplex, up to 300 m on OM3; DOM supported.",
         compatible="All Voltaris SFP+ ports: VX-NET-S24, VX-NET-S48X, VX-SRV-R250, VX-SRV-R450, VX-STO-N16, VX-NET-FW200.",
         substitutes="None.",
         cross_sell="Always quoted with VX-NET-S48X and with SFP+ server/NAS links."),
    dict(sku="VX-NET-AP6", name="Voltaris AP6 Wi-Fi 6 Access Point", category="Networking",
         list_price=349.00, lifecycle="End of life — last-time-buy, no further production (EOL announced 2026-06-30)",
         warranty="Limited lifetime; firmware support until 2029-06-30",
         summary="Ceiling-mount Wi-Fi 6 (802.11ax) AP for offices and warehouses.",
         specs="2x2 dual-band 802.11ax, up to 3.0 Gbps aggregate; 1x 1GbE; PoE (802.3af) powered; "
               "cloud or controller managed; indoor, IP42.",
         compatible="VX-NET-S24 (PoE).",
         substitutes="VX-NET-AP7 — the direct successor; same mounting bracket, same management platform, "
                     "mixes with AP6 in one network.",
         cross_sell="VX-NET-S24 for PoE."),
    dict(sku="VX-NET-AP7", name="Voltaris AP7 Wi-Fi 7 Access Point", category="Networking",
         list_price=529.00, lifecycle="Active", warranty="Limited lifetime",
         summary="Tri-band Wi-Fi 7 (802.11be) AP — successor to the AP6 — for high-density offices, "
                 "warehouses, retail and campuses.",
         specs="4x4 tri-band 2.4/5/6 GHz 802.11be, up to 9.3 Gbps aggregate; 1x 2.5GbE; PoE+ (802.3at) "
               "powered; uses the AP6 mounting bracket; cloud or controller managed; indoor, IP42.",
         compatible="VX-NET-S24 (PoE+), VX-NET-AP6 (mixed deployments supported).",
         substitutes="VX-NET-AP6 only while last-time-buy stock lasts (lower performance, no 6 GHz).",
         cross_sell="VX-NET-S24 PoE+ switches; VX-NET-FW200 per site."),
    dict(sku="VX-NET-FW200", name="Voltaris FW200 Firewall Appliance", category="Networking",
         list_price=1840.00, lifecycle="Active", warranty="3 years advance replacement; security subscription sold separately",
         summary="Next-generation firewall for branches, stores and small campuses.",
         specs="5 Gbps firewall / 1.2 Gbps threat protection throughput; 8x 1GbE + 2x 10GbE SFP+; "
               "SD-WAN; site-to-site VPN; zero-touch provisioning; desktop or 1U rack kit.",
         compatible="VX-NET-S24, VX-SFP-10G-SR.",
         substitutes="None in the current range.",
         cross_sell="One per site with VX-NET-S24 and VX-NET-AP7 rollouts."),
    dict(sku="VX-LAP-E14", name="Voltaris E14 Business Laptop", category="Endpoint",
         list_price=1149.00, lifecycle="Active", warranty="1 year carry-in (3-year onsite upgrade available)",
         summary="14\" business laptop for office staff, students and field teams.",
         specs="14\" 1920x1200 IPS; 10-core CPU; 16 GB RAM; 512 GB NVMe; Wi-Fi 6E; 2x USB-C/Thunderbolt 4; "
               "1.35 kg; 12 h battery; TPM 2.0.",
         compatible="VX-DOCK-TB4, VX-MON-27Q, VX-MON-34W.",
         substitutes="VX-LAP-P16 for engineering/CAD users (heavier, much higher price).",
         cross_sell="VX-DOCK-TB4 + VX-MON-27Q desk setup."),
    dict(sku="VX-LAP-P16", name="Voltaris P16 Mobile Workstation", category="Endpoint",
         list_price=3290.00, lifecycle="Active", warranty="3 years onsite",
         summary="16\" ISV-certified mobile workstation for CAD, simulation and content creation.",
         specs="16\" 3840x2400 OLED; 16-core CPU; 64 GB RAM; 2 TB NVMe; professional GPU with 12 GB; "
               "Wi-Fi 7; 2x Thunderbolt 4; 2.4 kg; ISV-certified for major CAD suites.",
         compatible="VX-DOCK-TB4, VX-MON-34W, VX-MON-27Q.",
         substitutes="No equivalent mobile workstation; VX-DSK-M5 is NOT a substitute for CAD workloads. "
                     "VX-LAP-E14 only as a temporary loaner for non-CAD work.",
         cross_sell="VX-DOCK-TB4 + VX-MON-34W engineering desk setup."),
    dict(sku="VX-DSK-M5", name="Voltaris M5 Mini Desktop", category="Endpoint",
         list_price=749.00, lifecycle="Active", warranty="3 years onsite",
         summary="1-litre mini PC for point-of-sale back offices, kiosks, reception desks and hot desks.",
         specs="8-core CPU; 16 GB RAM; 512 GB NVMe; 2x DisplayPort + HDMI; 1x 2.5GbE; Wi-Fi 6E; "
               "VESA mount included.",
         compatible="VX-MON-27Q (VESA mount behind the monitor), VX-MON-34W.",
         substitutes="VX-LAP-E14 where mobility is required.",
         cross_sell="VX-MON-27Q (one per M5)."),
    dict(sku="VX-MON-27Q", name="Voltaris 27Q 27\" QHD Monitor", category="Endpoint",
         list_price=329.00, lifecycle="Active", warranty="3 years advance replacement",
         summary="27\" QHD office monitor with height-adjustable stand.",
         specs="27\" 2560x1440 IPS, 75 Hz; USB-C 65 W power delivery; DisplayPort, HDMI; VESA 100; "
               "M5 mounting bracket included.",
         compatible="VX-LAP-E14, VX-LAP-P16, VX-DSK-M5, VX-DOCK-TB4.",
         substitutes="VX-MON-34W for more screen area.",
         cross_sell="VX-DOCK-TB4 for laptop users."),
    dict(sku="VX-MON-34W", name="Voltaris 34W 34\" Ultrawide USB-C Monitor", category="Endpoint",
         list_price=689.00, lifecycle="Active", warranty="3 years advance replacement",
         summary="34\" curved ultrawide for engineering, finance and multi-window work.",
         specs="34\" 3440x1440 IPS, 100 Hz; USB-C 90 W power delivery with built-in KVM; 2.5GbE port; "
               "DisplayPort, HDMI; factory-calibrated.",
         compatible="VX-LAP-E14, VX-LAP-P16, VX-DSK-M5, VX-DOCK-TB4.",
         substitutes="VX-MON-27Q (smaller, lower price).",
         cross_sell="VX-DOCK-TB4."),
    dict(sku="VX-DOCK-TB4", name="Voltaris TB4 Thunderbolt Dock", category="Endpoint",
         list_price=249.00, lifecycle="Active", warranty="3 years advance replacement",
         summary="Single-cable Thunderbolt 4 dock for laptops.",
         specs="Thunderbolt 4 / USB4 host; 96 W charging; 2x DisplayPort 1.4; 1x 2.5GbE; 4x USB-A, 2x USB-C; "
               "drives up to two 4K displays.",
         compatible="VX-LAP-E14, VX-LAP-P16, VX-MON-27Q, VX-MON-34W.",
         substitutes="None.",
         cross_sell="Sold with every E14/P16 desk setup."),
    dict(sku="VX-UPS-1500", name="Voltaris UPS-1500 Rack UPS", category="Datacenter",
         list_price=1090.00, lifecycle="Active", warranty="3 years (2 years on batteries)",
         summary="1,500 VA / 1,350 W line-interactive 2U UPS for server and network racks.",
         specs="1,500 VA / 1,350 W; 2U; 8x C13 outlets; hot-swap batteries; network management card "
               "included; ~10 min runtime at 800 W.",
         compatible="VX-RACK-42U, VX-SRV-R250 (up to two), VX-SRV-R450 (one per two servers), VX-STO-N16, VX-NET-S48X.",
         substitutes="None in the current range.",
         cross_sell="Recommended with every new server or NAS rack deployment."),
    dict(sku="VX-RACK-42U", name="Voltaris 42U Server Rack Cabinet", category="Datacenter",
         list_price=1450.00, lifecycle="Active", warranty="5 years",
         summary="600x1200 mm 42U cabinet for server rooms.",
         specs="42U, 600 mm wide x 1200 mm deep; perforated front/rear doors; 1,300 kg static load; "
               "side panels with locks; cable management kit; 2x 0U PDU mounts.",
         compatible="All Voltaris rack-mount products (R250, R450, N16, S48X, UPS-1500, FW200 rack kit).",
         substitutes="None.",
         cross_sell="VX-UPS-1500."),
]
P = {p["sku"]: p for p in PRODUCTS}

# Price tiers apply only when the client has no framework contract in force.
TIER_10_PCT, TIER_50_PCT = 3, 6

# ── Clients, contacts, Voltaris account managers ───────────────────────────
ACCOUNT_MANAGERS = {
    "AM-01": dict(name="Elise Maes", email="elise.maes@voltaris.example", region="Benelux"),
    "AM-02": dict(name="Thomas Girard", email="thomas.girard@voltaris.example", region="France & Ireland"),
}
CLIENTS = [
    dict(id="C-1001", name="Brightwater Logistics NV", industry="Logistics & warehousing",
         country="Belgium", address="Noorderlaan 140, 2030 Antwerpen", tier="Gold", am="AM-01",
         since="2019-04-15", spend_2025=412_600, sites="HQ Antwerp; warehouses Antwerp-Port, Ghent (opening Q1 2027), Liège (opening Q1 2027)"),
    dict(id="C-1002", name="Meridian Health Group", industry="Healthcare (hospital group, 4 sites)",
         country="France", address="18 Rue Garibaldi, 69006 Lyon", tier="Platinum", am="AM-02",
         since="2017-09-01", spend_2025=968_300, sites="Lyon (HQ + main hospital), Villeurbanne, Grenoble, Annecy"),
    dict(id="C-1003", name="Kestrel Engineering BV", industry="Engineering consultancy (mechanical & civil)",
         country="Netherlands", address="Strijp-S, Torenallee 32, 5617 BD Eindhoven", tier="Silver", am="AM-01",
         since="2022-02-10", spend_2025=138_900, sites="Eindhoven office (85 staff)"),
    dict(id="C-1004", name="Aurora Retail Group SA", industry="Retail (fashion & home, 120 stores)",
         country="Luxembourg", address="12 Rue Eugène Ruppert, 2453 Luxembourg", tier="Gold", am="AM-01",
         since="2020-06-01", spend_2025=587_400, sites="HQ Luxembourg; 120 stores in LU/BE/FR/DE; 20 new stores planned 2027"),
    dict(id="C-1005", name="Pinecrest University", industry="Higher education & research",
         country="Ireland", address="Pinecrest Campus, Belfield Road, Dublin 4", tier="Silver", am="AM-02",
         since="2023-01-20", spend_2025=244_100, sites="Main campus Dublin (Science Building, Library, IT Services)"),
]
C = {c["id"]: c for c in CLIENTS}

CONTACTS = [
    dict(id="CT-01", client="C-1001", name="Lena Verhoeven", title="IT Procurement Manager",
         email="lena.verhoeven@brightwater-logistics.example", phone="+32 3 555 01 21", primary="yes"),
    dict(id="CT-02", client="C-1001", name="Marc De Smet", title="Infrastructure Lead",
         email="marc.desmet@brightwater-logistics.example", phone="+32 3 555 01 48", primary="no"),
    dict(id="CT-03", client="C-1002", name="Claire Fontaine", title="Head of IT Operations",
         email="claire.fontaine@meridian-health.example", phone="+33 4 55 50 12 30", primary="yes"),
    dict(id="CT-04", client="C-1002", name="Julien Moreau", title="Procurement Officer",
         email="julien.moreau@meridian-health.example", phone="+33 4 55 50 12 77", primary="no"),
    dict(id="CT-05", client="C-1003", name="Pieter van Dijk", title="CTO",
         email="pieter.vandijk@kestrel-eng.example", phone="+31 40 555 0190", primary="yes"),
    dict(id="CT-06", client="C-1003", name="Sanne Bakker", title="Office & Facilities Manager",
         email="sanne.bakker@kestrel-eng.example", phone="+31 40 555 0112", primary="no"),
    dict(id="CT-07", client="C-1004", name="Sophie Klein", title="Head of Store Technology",
         email="sophie.klein@aurora-retail.example", phone="+352 555 340 10", primary="yes"),
    dict(id="CT-08", client="C-1004", name="Ruben Weber", title="IT Purchasing Lead",
         email="ruben.weber@aurora-retail.example", phone="+352 555 340 44", primary="no"),
    dict(id="CT-09", client="C-1005", name="Aoife Byrne", title="Research Computing Manager",
         email="aoife.byrne@pinecrest.example", phone="+353 1 555 7720", primary="yes"),
    dict(id="CT-10", client="C-1005", name="Conor Walsh", title="Procurement Officer",
         email="conor.walsh@pinecrest.example", phone="+353 1 555 7704", primary="no"),
]
CN = {c["id"]: c for c in CONTACTS}

# ── Contracts ──────────────────────────────────────────────────────────────
CONTRACTS = [
    dict(id="FA-2024-017", client="C-1001", type="Framework Supply Agreement", start="2024-03-01",
         end="2027-02-28", status="Active", disc=dict(Datacenter=8, Networking=12, Endpoint=6),
         payment="Net 45", incoterms="DAP customer site", sla="Next-business-day onsite (Datacenter & Networking)",
         notice="90 days before end date", price_protection="List prices frozen per contract year (March-February)",
         special="Volume commitment EUR 350k/year (2025 actual: EUR 412.6k — met). "
                 "Promotional pricing may replace (not stack with) the contract discount, whichever is better for the client."),
    dict(id="FA-2024-002", client="C-1002", type="Framework Supply & Service Agreement", start="2024-01-01",
         end="2026-12-31", status="Active — renewal window open", disc=dict(Datacenter=10, Networking=10, Endpoint=8),
         payment="Net 60", incoterms="DAP customer site",
         sla="4-hour onsite for Datacenter products at hospital sites; next-business-day for all other products",
         notice="Renewal or termination notice due by 2026-11-01 (60 days before end date); auto-renews for 12 months on unchanged terms if no notice",
         price_protection="12-month price protection on quoted configurations",
         special="Healthcare data clause: failed storage drives are retained by the client (no return), "
                 "replacement shipped without return requirement. Purchase orders must reference a Meridian PO number before release."),
    dict(id="FA-2025-031", client="C-1003", type="Framework Supply Agreement", start="2025-05-01",
         end="2027-04-30", status="Active", disc=dict(Datacenter=6, Networking=6, Endpoint=9),
         payment="Net 30", incoterms="DAP customer site", sla="Next-business-day onsite",
         notice="60 days before end date", price_protection="None",
         special="Early-life failure clause: any endpoint failing within 30 days of delivery is swapped for a new unit, not repaired."),
    dict(id="FA-2022-009", client="C-1004", type="Framework Supply Agreement", start="2022-07-01",
         end="2026-06-30", status="Expired", disc=dict(Datacenter=9, Networking=10, Endpoint=10),
         payment="Net 45", incoterms="DAP Luxembourg HQ or store", sla="Next-business-day advance replacement",
         notice="90 days before end date (lapsed without renewal)", price_protection="None",
         special="Expired 2026-06-30. Since 2026-07-01 Aurora orders are priced at list with standard volume tiers "
                 "(3% at 10+ units, 6% at 50+ units per SKU) and standard payment terms (Net 30). "
                 "Renewal FA-2026-022 is drafted and awaiting the client's signature."),
    dict(id="FA-2026-022", client="C-1004", type="Framework Supply Agreement (renewal of FA-2022-009)", start="2026-11-01",
         end="2029-10-31", status="Draft — sent to client 2026-09-18, awaiting signature",
         disc=dict(Datacenter=9, Networking=12, Endpoint=10), payment="Net 45", incoterms="DAP Luxembourg HQ or store",
         sla="Next-business-day advance replacement", notice="90 days before end date",
         price_protection="List prices frozen for 12 months from start date",
         special="Not yet in force. Proposed goodwill credit: the difference between list-tier pricing and the "
                 "old FA-2022-009 discounts on orders placed 2026-07-01 to 2026-10-31, credited on signature."),
    dict(id="EA-2025-012", client="C-1005", type="Education Framework Agreement (public tender PU-2025-ICT-04)",
         start="2025-09-01", end="2028-08-31", status="Active", disc=dict(Datacenter=15, Networking=15, Endpoint=15),
         payment="Net 30", incoterms="DAP Pinecrest campus (named building loading dock)", sla="Next-business-day onsite",
         notice="Tender-governed: no auto-renewal; re-tender required", price_protection="Tender prices fixed for the full term on awarded lots",
         special="Delivery address changes must be requested in writing by the Procurement Officer at least "
                 "2 business days before dispatch. Orders above EUR 100k need a separate mini-competition."),
]


def contract_in_force(client_id: str, on: str) -> dict | None:
    for ct in CONTRACTS:
        if ct["client"] == client_id and ct["start"] <= on <= ct["end"] and not ct["status"].startswith("Draft"):
            return ct
    return None


def unit_price(sku: str, qty: int, client_id: str, on: str) -> tuple[float, str]:
    """Net unit price and the pricing basis a quote/order on date ``on`` gets."""
    p = P[sku]
    ct = contract_in_force(client_id, on)
    if ct:
        pct = ct["disc"][p["category"]]
        return round(p["list_price"] * (1 - pct / 100), 2), f"{ct['id']} ({pct}% {p['category']})"
    pct = TIER_50_PCT if qty >= 50 else TIER_10_PCT if qty >= 10 else 0
    return round(p["list_price"] * (1 - pct / 100), 2), f"List price, volume tier {pct}%"


# ── Orders ────────────────────────────────────────────────────────────────
# line: (sku, qty, qty_shipped)   qty_backordered = qty - shipped for backorders
ORDERS = [
    dict(id="SO-23110", client="C-1005", contact="CT-10", po="PU-PO-25-0871", date="2025-10-14",
         status="Delivered", ship="2025-10-20", delivered="2025-10-22", carrier="DHL Freight", tracking="DHLF-7741029",
         ship_to="Pinecrest University, IT Services, Belfield Road, Dublin 4",
         lines=[("VX-STO-N16", 1, 1), ("VX-HDD-16T", 16, 16), ("VX-SFP-10G-SR", 4, 4)],
         note="Research data NAS (installed in IT Services server room)."),
    dict(id="SO-23402", client="C-1004", contact="CT-08", po="AUR-2026-0114", date="2026-01-20",
         status="Delivered", ship="2026-01-27", delivered="2026-01-29", carrier="DB Schenker", tracking="DBS-3390218",
         ship_to="Aurora Retail Group, Central Logistics, Rue de Bitbourg 9, 1273 Luxembourg",
         lines=[("VX-NET-FW200", 40, 40), ("VX-NET-S24", 40, 40)],
         note="Store network refresh wave 1 (40 stores)."),
    dict(id="SO-24581", client="C-1001", contact="CT-01", po="BWL-PO-26-311", date="2026-08-04",
         status="Delivered", ship="2026-08-10", delivered="2026-08-12", carrier="DPD", tracking="DPD-05512873345",
         ship_to="Brightwater Logistics, Warehouse Antwerp-Port, Haven 1050, 2030 Antwerpen",
         lines=[("VX-NET-AP6", 40, 40), ("VX-NET-S24", 4, 4)],
         note="AP6 last-time-buy quantity for Antwerp-Port warehouse."),
    dict(id="SO-24633", client="C-1002", contact="CT-04", po="MHG-PO-2026-1187", date="2026-08-21",
         status="Delivered", ship="2026-08-27", delivered="2026-08-31", carrier="DB Schenker", tracking="DBS-3512244",
         ship_to="Meridian Health Group, Main Hospital Data Centre, 18 Rue Garibaldi, 69006 Lyon",
         lines=[("VX-SRV-R450", 2, 2), ("VX-STO-N16", 1, 1), ("VX-HDD-16T", 16, 16), ("VX-UPS-1500", 1, 1)],
         note="PACS imaging archive expansion, Lyon."),
    dict(id="SO-24702", client="C-1003", contact="CT-05", po="KES-0926", date="2026-09-08",
         status="Partially shipped — backorder", ship="2026-09-24", delivered="2026-09-25", carrier="PostNL Pakket", tracking="PNL-3SKES0926A",
         ship_to="Kestrel Engineering, Torenallee 32, 5617 BD Eindhoven",
         lines=[("VX-LAP-P16", 6, 2), ("VX-DOCK-TB4", 6, 6), ("VX-MON-34W", 6, 6)],
         note="Workstations for 6 new engineers starting 2026-10-05. 4x P16 on backorder, "
              "allocated first from the inbound P16 receipt (see stock incoming ETA)."),
    dict(id="SO-24718", client="C-1004", contact="CT-08", po="AUR-2026-0907", date="2026-09-15",
         status="Shipped — in transit", ship="2026-09-29", delivered="", carrier="DB Schenker", tracking="DBS-3601877",
         ship_to="Aurora Retail Group, Central Logistics, Rue de Bitbourg 9, 1273 Luxembourg",
         lines=[("VX-DSK-M5", 30, 30), ("VX-MON-27Q", 30, 30), ("VX-NET-S24", 15, 15)],
         note="Store back-office refresh, 15 stores (rollout starts 2026-10-06). Expected delivery 2026-10-03. "
              "Priced at list with volume tiers — FA-2022-009 expired 2026-06-30."),
    dict(id="SO-24750", client="C-1005", contact="CT-10", po="PU-PO-26-1342", date="2026-09-22",
         status="Processing — picking scheduled 2026-10-05", ship="", delivered="", carrier="DHL Freight", tracking="",
         ship_to="Pinecrest University, IT Services, Belfield Road, Dublin 4",
         lines=[("VX-LAP-E14", 60, 0), ("VX-STO-N16", 1, 0), ("VX-HDD-16T", 12, 0), ("VX-NET-AP7", 10, 0)],
         note="Student lab laptops + library NAS + Science Building Wi-Fi. Planned dispatch 2026-10-06. "
              "Stock fully allocated."),
    dict(id="SO-24771", client="C-1001", contact="CT-01", po="BWL-PO-26-402", date="2026-09-28",
         status="Confirmed — stock allocated", ship="", delivered="", carrier="DPD", tracking="",
         ship_to="Brightwater Logistics, Warehouse Ghent, Skaldenstraat 61, 9042 Gent",
         lines=[("VX-NET-AP7", 25, 0), ("VX-NET-FW200", 2, 0), ("VX-NET-S48X", 1, 0), ("VX-SFP-10G-SR", 4, 0)],
         note="Ghent warehouse pilot. Planned dispatch 2026-10-07, delivery 2026-10-08 "
              "(client needs it by 2026-10-09)."),
    dict(id="SO-24779", client="C-1002", contact="CT-04", po="(pending)", date="2026-09-30",
         status="On hold — awaiting client PO", ship="", delivered="", carrier="DB Schenker", tracking="",
         ship_to="Meridian Health Group, Grenoble Site, 5 Avenue du Vercors, 38000 Grenoble",
         lines=[("VX-SSD-3840", 4, 0), ("VX-SRV-R250", 1, 0)],
         note="Stock reserved until 2026-10-14; released automatically if no PO number by then "
              "(FA-2024-002 requires a Meridian PO before release)."),
    dict(id="SO-24790", client="C-1003", contact="CT-06", po="KES-0931", date="2026-10-01",
         status="Cancelled", ship="", delivered="", carrier="", tracking="",
         ship_to="Kestrel Engineering, Torenallee 32, 5617 BD Eindhoven",
         lines=[("VX-DSK-M5", 2, 0)],
         note="Cancelled by client on 2026-10-01 before picking (ordered by mistake) — no fee. "
              "Allocation released the same day."),
]
OPEN_STATUSES = ("Processing", "Confirmed", "On hold")  # stock is reserved for these

# ── Stock (on hand AFTER every shipment above) ─────────────────────────────
STOCK = {  # sku: (on_hand, reorder_point, incoming_qty, incoming_eta)
    "VX-SRV-R250": (3, 4, 10, "2026-10-20"),
    "VX-SRV-R450": (14, 6, 0, ""),
    "VX-STO-N8": (22, 6, 0, ""),
    "VX-STO-N16": (5, 3, 4, "2026-10-27"),
    "VX-SSD-3840": (48, 20, 0, ""),
    "VX-HDD-16T": (210, 80, 0, ""),
    "VX-NET-S24": (64, 25, 0, ""),
    "VX-NET-S48X": (9, 3, 0, ""),
    "VX-SFP-10G-SR": (180, 60, 0, ""),
    "VX-NET-AP6": (12, 0, 0, ""),
    "VX-NET-AP7": (70, 40, 150, "2026-11-05"),
    "VX-NET-FW200": (26, 10, 0, ""),
    "VX-LAP-E14": (85, 40, 0, ""),
    "VX-LAP-P16": (0, 6, 20, "2026-10-14"),
    "VX-DSK-M5": (40, 20, 0, ""),
    "VX-MON-27Q": (55, 25, 0, ""),
    "VX-MON-34W": (18, 8, 0, ""),
    "VX-DOCK-TB4": (120, 40, 0, ""),
    "VX-UPS-1500": (11, 5, 0, ""),
    "VX-RACK-42U": (6, 2, 0, ""),
}
assert set(STOCK) == set(P)

MOVEMENTS = [  # date, type, sku, qty_change(on_hand), reference, note
    ("2026-08-10", "Shipment", "VX-NET-AP6", -40, "SO-24581", "Shipped to Brightwater Antwerp-Port"),
    ("2026-08-10", "Shipment", "VX-NET-S24", -4, "SO-24581", "Shipped to Brightwater Antwerp-Port"),
    ("2026-08-27", "Shipment", "VX-SRV-R450", -2, "SO-24633", "Shipped to Meridian Lyon"),
    ("2026-08-27", "Shipment", "VX-STO-N16", -1, "SO-24633", "Shipped to Meridian Lyon"),
    ("2026-08-27", "Shipment", "VX-HDD-16T", -16, "SO-24633", "Shipped to Meridian Lyon"),
    ("2026-08-27", "Shipment", "VX-UPS-1500", -1, "SO-24633", "Shipped to Meridian Lyon"),
    ("2026-09-03", "Receipt", "VX-NET-AP7", 60, "PO-SUP-8812", "Supplier receipt"),
    ("2026-09-16", "Receipt", "VX-LAP-E14", 50, "PO-SUP-8840", "Supplier receipt"),
    ("2026-09-24", "Shipment", "VX-LAP-P16", -2, "SO-24702", "Partial shipment to Kestrel; 4 units backordered, P16 now 0 on hand"),
    ("2026-09-24", "Shipment", "VX-DOCK-TB4", -6, "SO-24702", "Shipped to Kestrel"),
    ("2026-09-24", "Shipment", "VX-MON-34W", -6, "SO-24702", "Shipped to Kestrel"),
    ("2026-09-29", "Shipment", "VX-DSK-M5", -30, "SO-24718", "Shipped to Aurora Central Logistics"),
    ("2026-09-29", "Shipment", "VX-MON-27Q", -30, "SO-24718", "Shipped to Aurora Central Logistics"),
    ("2026-09-29", "Shipment", "VX-NET-S24", -15, "SO-24718", "Shipped to Aurora Central Logistics"),
    ("2026-10-01", "Allocation released", "VX-DSK-M5", 0, "SO-24790", "Order cancelled by client; 2 units back to available"),
]

# ── Customer engagement: tickets and emails ────────────────────────────────
TICKETS = [
    dict(id="TCK-2874", client="C-1005", contact="CT-09", opened="2025-11-18", closed="2025-11-20", status="Closed",
         channel="Email", subject="Drive failure in N16 (bay 7)", order="SO-23110", sku="VX-HDD-16T", priority="Normal",
         summary="One HDD failed 4 weeks after install; RAID 6 rebuilt on hot spare. Replacement drive shipped under warranty."),
    dict(id="TCK-2960", client="C-1004", contact="CT-07", opened="2026-02-09", closed="2026-02-11", status="Closed",
         channel="Phone", subject="FW200 zero-touch provisioning for stores", order="SO-23402", sku="VX-NET-FW200", priority="Normal",
         summary="Helped Store Technology set up zero-touch templates for the 40 wave-1 stores. Client very satisfied."),
    dict(id="TCK-3101", client="C-1001", contact="CT-02", opened="2026-08-13", closed="2026-08-14", status="Closed",
         channel="Email", subject="3 AP6 units not adopting in controller", order="SO-24581", sku="VX-NET-AP6", priority="High",
         summary="Units shipped with older firmware; resolved remotely with firmware 6.4.2. No hardware fault."),
    dict(id="TCK-3122", client="C-1002", contact="CT-03", opened="2026-08-25", closed="2026-08-26", status="Closed",
         channel="Email", subject="PSU fan warning on new R450", order="SO-24633", sku="VX-SRV-R450", priority="Critical",
         summary="BMC reported PSU2 fan fault. Replacement PSU delivered onsite within 4 h under FA-2024-002 SLA."),
    dict(id="TCK-3150", client="C-1004", contact="CT-08", opened="2026-09-16", closed="", status="Open — escalated to Contracts",
         channel="Email", subject="Pricing on SO-24718 higher than previous orders", order="SO-24718", sku="", priority="High",
         summary="Client asks why prices rose vs SO-23402. Cause: FA-2022-009 expired 2026-06-30; renewal FA-2026-022 awaiting their signature. Client unhappy."),
    dict(id="TCK-3165", client="C-1005", contact="CT-09", opened="2026-09-25", closed="2026-09-25", status="Closed",
         channel="Email", subject="N16 max capacity and SFP+ support", order="SO-23110", sku="VX-STO-N16", priority="Low",
         summary="Answered: 256 TB raw with 16x 16 TB; 2x 10GbE SFP+ onboard."),
    dict(id="TCK-3171", client="C-1003", contact="CT-06", opened="2026-09-26", closed="", status="Open",
         channel="Email", subject="Only 2 of 6 P16 workstations received", order="SO-24702", sku="VX-LAP-P16", priority="High",
         summary="4 units backordered; new engineers start 2026-10-05. Client needs a delivery date (and possibly loaners)."),
    dict(id="TCK-3176", client="C-1004", contact="CT-07", opened="2026-09-29", closed="2026-09-29", status="Closed",
         channel="Phone", subject="Tracking for SO-24718", order="SO-24718", sku="", priority="Normal",
         summary="Provided DB Schenker tracking DBS-3601877; expected delivery 2026-10-03."),
    dict(id="TCK-3185", client="C-1003", contact="CT-06", opened="2026-10-01", closed="2026-10-01", status="Closed",
         channel="Email", subject="Cancel order KES-0931 (2x M5)", order="SO-24790", sku="VX-DSK-M5", priority="Normal",
         summary="Cancelled before picking, no fee."),
    dict(id="TCK-3188", client="C-1001", contact="CT-01", opened="2026-10-01", closed="", status="Open",
         channel="Email", subject="Ship date for SO-24771 (Ghent pilot)", order="SO-24771", sku="", priority="High",
         summary="Client needs the Ghent pilot kit on site by 2026-10-09."),
    dict(id="TCK-3190", client="C-1002", contact="CT-03", opened="2026-10-01", closed="", status="Open",
         channel="Email", subject="Can the 3.84 TB NVMe SSDs go in the N16?", order="SO-24779", sku="VX-SSD-3840", priority="Normal",
         summary="Client asks whether the SSDs on SO-24779 can be used in the N16 at Lyon as well as the R250."),
    dict(id="TCK-3195", client="C-1005", contact="CT-10", opened="2026-10-02", closed="", status="Open",
         channel="Email", subject="Delivery address change for SO-24750", order="SO-24750", sku="", priority="Normal",
         summary="Wants delivery to Science Building loading dock instead of IT Services."),
]

SUPPORT = "support@voltaris.example"
EMAILS = [
    ("E-01", "2026-08-13 09:12", "CT-02", SUPPORT, "AP6 units not showing up in controller", "TCK-3101",
     "Hi Voltaris support,\n\nWe installed the 40 AP6s from order SO-24581 at Antwerp-Port yesterday. 37 are fine, "
     "but 3 never adopt in the controller — they power up and the LED stays amber. Can you help today? "
     "The warehouse goes live on Monday.\n\nThanks,\nMarc De Smet\nInfrastructure Lead, Brightwater Logistics"),
    ("E-02", "2026-08-25 07:48", "CT-03", SUPPORT, "URGENT: PSU fan warning on new R450 (Lyon)", "TCK-3122",
     "Hello,\n\nOne of the two R450 servers delivered on order SO-24633 is reporting a PSU2 fan fault in the BMC. "
     "This server hosts part of our imaging archive. Please send someone under our 4-hour SLA.\n\n"
     "Claire Fontaine\nHead of IT Operations, Meridian Health Group"),
    ("E-03", "2026-09-02 16:30", "CT-07", "elise.maes@voltaris.example", "2027 store openings — early heads-up", "",
     "Hi Elise,\n\nQuick heads-up for planning: the board approved 20 new stores for 2027, and we are evaluating a "
     "Wi-Fi refresh across the existing estate at the same time (our current store Wi-Fi is third-party and five years old). "
     "I'd like to understand what a standard store kit (firewall, switch, access points, back-office PC) would look like "
     "from you. No rush — Q4 is fine.\n\nBest,\nSophie Klein\nHead of Store Technology, Aurora Retail Group"),
    ("E-04", "2026-09-10 11:05", "CT-05", "elise.maes@voltaris.example", "Confirming 6x P16 for new hires", "",
     "Elise,\n\nConfirming our PO KES-0926 for six P16 workstations with docks and 34\" monitors. "
     "Six engineers start on 5 October, so delivery before then is essential.\n\nRegards,\nPieter van Dijk\nCTO, Kestrel Engineering"),
    ("E-05", "2026-09-16 14:22", "CT-08", SUPPORT, "Invoice for AUR-2026-0907 — prices higher?", "TCK-3150",
     "Hello,\n\nThe order confirmation for our PO AUR-2026-0907 (your SO-24718) shows prices noticeably higher than "
     "what we paid in January (SO-23402). For example the S24 switches. Has something changed? "
     "We have always had a framework discount with you.\n\nRuben Weber\nIT Purchasing Lead, Aurora Retail Group"),
    ("E-06", "2026-09-18 10:40", "CT-10", "thomas.girard@voltaris.example", "PU-PO-26-1342 — student lab order", "",
     "Dear Thomas,\n\nPlease find attached PO PU-PO-26-1342 under the education framework (tender PU-2025-ICT-04): "
     "60 E14 laptops, one N16 with 12 drives for the library, and 10 AP7 access points for the Science Building.\n\n"
     "Kind regards,\nConor Walsh\nProcurement Officer, Pinecrest University"),
    ("E-07", "2026-09-24 08:55", "CT-01", "elise.maes@voltaris.example", "Wi-Fi for Ghent and Liège warehouses", "",
     "Hi Elise,\n\nWe are opening two new warehouses (Ghent and Liège) in Q1 2027 and need roughly 60 access points across "
     "both, plus a firewall and PoE switches per site. Since the AP6 is end-of-life, should we standardise on the AP7? "
     "Can it run alongside the AP6s in Antwerp-Port? Ghent pilot order is coming separately.\n\nThanks,\nLena Verhoeven\n"
     "IT Procurement Manager, Brightwater Logistics"),
    ("E-08", "2026-09-25 13:17", "CT-09", SUPPORT, "N16 capacity question", "TCK-3165",
     "Hi,\n\nFor the N16 we bought last year (SO-23110): what is the maximum raw capacity if we fill it with your 16 TB drives, "
     "and does it have SFP+ onboard or do we need a card?\n\nThanks,\nAoife Byrne\nResearch Computing Manager, Pinecrest University"),
    ("E-09", "2026-09-26 09:03", "CT-06", SUPPORT, "Missing 4 P16 laptops!", "TCK-3171",
     "Hello,\n\nWe received the delivery for KES-0926 yesterday but only 2 of the 6 P16 workstations were in it "
     "(all docks and monitors arrived). Our new engineers start on 5 October. When will the other 4 arrive?\n\n"
     "Sanne Bakker\nOffice & Facilities Manager, Kestrel Engineering"),
    ("E-10", "2026-09-29 15:41", "CT-07", SUPPORT, "Tracking for store back-office kit", "TCK-3176",
     "Hi, could you send tracking for our order SO-24718? Store rollout starts 6 October. Thanks, Sophie Klein"),
    ("E-11", "2026-09-30 10:12", "CT-09", "thomas.girard@voltaris.example", "Budgetary pricing — research compute cluster 2027", "",
     "Dear Thomas,\n\nGood news: our physics and genomics groups have been awarded a research infrastructure grant. "
     "We need budgetary pricing for a small compute cluster in early 2027 — we are thinking 8 R450 servers, a 10G switch "
     "and whatever racks/UPS that implies. Some nodes will need GPUs later. Budget submission deadline is 2026-10-30.\n\n"
     "Best regards,\nAoife Byrne\nResearch Computing Manager, Pinecrest University"),
    ("E-12", "2026-09-30 17:26", "CT-04", "thomas.girard@voltaris.example", "SO-24779 on hold + contract renewal", "",
     "Bonjour Thomas,\n\nThe PO for SO-24779 (Grenoble R250 + SSDs) is still in internal approval — please keep the "
     "order on hold, we expect the PO number next week. Separately, our framework agreement ends on 31 December. "
     "We would like to discuss the renewal and possibly include a second N16 for the Grenoble imaging archive in the "
     "same negotiation.\n\nCordialement,\nJulien Moreau\nProcurement Officer, Meridian Health Group"),
    ("E-13", "2026-10-01 08:20", "CT-06", SUPPORT, "Please cancel KES-0931", "TCK-3185",
     "Hi, please cancel our order KES-0931 for 2 M5 mini PCs — it was placed by mistake. Thanks, Sanne Bakker"),
    ("E-14", "2026-10-01 11:47", "CT-01", SUPPORT, "When does SO-24771 ship?", "TCK-3188",
     "Hello,\n\nOur Ghent pilot order SO-24771 is confirmed — can you tell me when it ships? We need everything on site "
     "by 9 October for the pilot.\n\nThanks,\nLena Verhoeven"),
    ("E-15", "2026-10-01 14:05", "CT-03", SUPPORT, "SSD compatibility question", "TCK-3190",
     "Hi,\n\nThe four 3.84 TB SSDs on SO-24779 are meant for the Grenoble R250. Could the same SSD model also go into "
     "the N16 we have in Lyon to speed it up? How many can it take?\n\nClaire Fontaine"),
    ("E-16", "2026-10-02 09:30", "CT-10", SUPPORT, "Delivery address change — PU-PO-26-1342", "TCK-3195",
     "Dear Support,\n\nFor our order PU-PO-26-1342 (SO-24750), could the delivery go to the Science Building loading dock "
     "(Science Building, Belfield Road, Dublin 4) instead of IT Services? The labs are there.\n\nKind regards,\nConor Walsh"),
]

ACCOUNT_NOTES = {
    "C-1001": [
        "Expanding: Ghent + Liège warehouses open Q1 2027 (~60 APs, firewall + PoE switches per site) — see E-07.",
        "AP6 estate at Antwerp-Port (40 units, SO-24581). AP6 is EOL; AP7 is the successor and mixes with AP6.",
        "Ghent pilot SO-24771 is time-critical (on site by 2026-10-09). Treat any delay as an escalation.",
        "Relationship: strong. Lena prefers short, numbers-first emails.",
    ],
    "C-1002": [
        "Platinum account, largest by spend. Framework FA-2024-002 ends 2026-12-31; client raised renewal (E-12).",
        "Wants a second N16 for the Grenoble imaging archive — bundle into renewal discussion.",
        "SO-24779 on hold awaiting PO; reservation expires 2026-10-14.",
        "Very sensitive to downtime (hospitals). Last critical ticket (TCK-3122) resolved within SLA — client happy.",
    ],
    "C-1003": [
        "Small but growing engineering firm; heavy P16 workstation users (CAD).",
        "At risk: 4 P16s backordered on SO-24702 vs new hires starting 2026-10-05 (TCK-3171 open). "
        "Proactive loaner offer would protect the relationship.",
        "Pieter (CTO) is the decision maker; Sanne handles logistics.",
    ],
    "C-1004": [
        "At risk: unhappy about post-expiry pricing on SO-24718 (TCK-3150). Renewal FA-2026-022 awaits their signature "
        "and includes a goodwill credit — the fastest fix for the complaint.",
        "Big 2027 opportunity: 20 new stores + Wi-Fi refresh of the existing 120 stores (E-03). Current store Wi-Fi is third-party.",
        "Standard store kit today: 1x FW200, 1x S24, back-office M5 + 27Q.",
    ],
    "C-1005": [
        "Education framework EA-2025-012 (tender). Orders above EUR 100k need a mini-competition.",
        "Opportunity: research compute cluster 2027 — 8x R450 + 10G switch + racks/UPS, GPUs later (E-11). "
        "Budget submission deadline 2026-10-30.",
        "SO-24750 address change requested (TCK-3195) — needs written request from Procurement Officer (Conor Walsh is that person).",
    ],
}


# ── Rendering ──────────────────────────────────────────────────────────────
def _csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def build_orders() -> tuple[list[dict], list[dict], dict[str, int]]:
    orders, lines, reserved = [], [], {sku: 0 for sku in P}
    for o in ORDERS:
        total, bases = 0.0, set()
        for n, (sku, qty, shipped) in enumerate(o["lines"], 1):
            price, basis = unit_price(sku, qty, o["client"], o["date"])
            bases.add(basis.split(" (")[0] if basis.startswith(("FA", "EA")) else "List + volume tiers")
            backordered = qty - shipped if "backorder" in o["status"] else 0
            if o["status"] == "Cancelled":
                line_status = "Cancelled"
            elif shipped == qty:
                line_status = "Delivered" if o["delivered"] else "Shipped"
            elif backordered:
                line_status = f"{shipped} shipped, {backordered} backordered"
            else:
                line_status = "Allocated (reserved in stock)"
                if o["status"].startswith(OPEN_STATUSES):
                    reserved[sku] += qty
            line_total = round(price * qty, 2)
            if o["status"] != "Cancelled":
                total += line_total
            lines.append(dict(order_id=o["id"], line=n, sku=sku, product=P[sku]["name"], qty=qty,
                              qty_shipped=shipped, qty_backordered=backordered, unit_price_eur=f"{price:.2f}",
                              line_total_eur=f"{line_total:.2f}", pricing_basis=basis, line_status=line_status))
        cn = CN[o["contact"]]
        orders.append(dict(order_id=o["id"], client_id=o["client"], client=C[o["client"]]["name"],
                           ordered_by=cn["name"], client_po=o["po"], order_date=o["date"], status=o["status"],
                           ship_date=o["ship"], delivered_date=o["delivered"], carrier=o["carrier"],
                           tracking=o["tracking"], ship_to=o["ship_to"], pricing=" / ".join(sorted(bases)),
                           order_total_eur_excl_vat=f"{total:.2f}", notes=o["note"]))
    return orders, lines, reserved


def build_stock(reserved: dict[str, int]) -> list[dict]:
    rows = []
    for sku, (on_hand, rop, inc, eta) in STOCK.items():
        res = reserved[sku]
        assert res <= on_hand, f"{sku}: reserved {res} > on hand {on_hand}"
        avail = on_hand - res
        flag = "OUT OF STOCK" if avail == 0 else "Below reorder point" if avail < rop else "OK"
        if P[sku]["lifecycle"].startswith("End of life"):
            flag = "EOL — last-time-buy, no replenishment"
        rows.append(dict(sku=sku, product=P[sku]["name"], warehouse=WAREHOUSE, on_hand=on_hand, reserved=res,
                         available=avail, reorder_point=rop, incoming_qty=inc, incoming_eta=eta,
                         stock_flag=flag, last_updated="2026-10-01"))
    return rows


def build_products_md() -> str:
    out = [f"# {COMPANY} — Product Catalogue (2026 range)\n",
           "Descriptions, specifications, compatibility, substitutes and accessories for every SKU we sell. "
           "Prices and stock are NOT in this catalogue.\n"]
    for cat in ("Datacenter", "Networking", "Endpoint"):
        out.append(f"\n## {cat}\n")
        for p in PRODUCTS:
            if p["category"] != cat:
                continue
            out.append(f"\n### {p['sku']} — {p['name']}\n\n"
                       f"- **What it is:** {p['summary']}\n"
                       f"- **Key specs:** {p['specs']}\n"
                       f"- **Compatible with:** {p['compatible']}\n"
                       f"- **Substitutes:** {p['substitutes']}\n"
                       f"- **Recommended accessories / add-ons:** {p['cross_sell']}\n"
                       f"- **Warranty:** {p['warranty']}\n"
                       f"- **Lifecycle:** {p['lifecycle']}\n")
    return "".join(out)


def build_price_list() -> list[dict]:
    rows = []
    for p in PRODUCTS:
        lp = p["list_price"]
        rows.append(dict(sku=p["sku"], product=p["name"], category=p["category"], list_price_eur=f"{lp:.2f}",
                         tier_10plus_eur=f"{lp * (1 - TIER_10_PCT / 100):.2f}",
                         tier_50plus_eur=f"{lp * (1 - TIER_50_PCT / 100):.2f}",
                         lifecycle="EOL" if p["lifecycle"].startswith("End") else "Active",
                         cross_sell=p["cross_sell"]))
    return rows


PRICING_POLICY = f"""# {COMPANY} — Pricing & Proposal Policy (sales use only)

## How a net price is built
1. Start from the list price (price_list.csv, EUR, excl. VAT).
2. **Client with a framework contract in force** on the quote date: apply that contract's discount for the
   product's category (Datacenter / Networking / Endpoint). Volume tiers do NOT stack on a contract discount.
   Contract discounts and status are held by @ContractingAssistant — never assume them.
3. **Client without a contract in force** (none, expired, or only a draft renewal): apply volume tiers per SKU line —
   {TIER_10_PCT}% at 10+ units, {TIER_50_PCT}% at 50+ units — and standard terms (Net 30).
4. **Promotions** (below) replace the discount from step 2 or 3 on the eligible SKUs, whichever is better for the
   client. Never stack a promotion with a contract discount.
5. Discretionary discount: up to 3% extra on proposals above EUR 50,000 net, sales manager approval required above
   that. Always state it as a separate line, never fold it into the unit price.
6. Quotes are valid 30 days (see terms and conditions). Prices exclude VAT and exclude installation services.

## Active promotions
| Code | Offer | Eligible | Valid until |
|---|---|---|---|
| PROMO-WIFI7-Q4 | 15% off VX-NET-AP7 for customers migrating from AP6 or a third-party Wi-Fi estate | VX-NET-AP7, min. 20 units per order | 2026-12-31 |
| PROMO-RACKREADY | Free VX-RACK-42U with every 4x VX-SRV-R450 on one order | VX-SRV-R450 | 2026-12-31 |

## Cross-sell & up-sell playbook
| If the client buys / plans… | Propose |
|---|---|
| Access points (AP7) for a new site | VX-NET-S24 PoE+ switch per ~20 APs, VX-NET-FW200 per site |
| AP6 estate (EOL) | AP7 migration with PROMO-WIFI7-Q4 |
| R450 / R250 servers | VX-RACK-42U, VX-UPS-1500 (1 per 2 R450), VX-SFP-10G-SR optics, VX-NET-S48X for a 10G fabric |
| N8 / N16 NAS | VX-HDD-16T drives (NAS ships empty), VX-SSD-3840 cache (N16 only), VX-UPS-1500 |
| E14 / P16 laptops | VX-DOCK-TB4 + VX-MON-27Q (office) or VX-MON-34W (engineering) |
| Retail store kit | 1x VX-NET-FW200, 1x VX-NET-S24, 2-3x VX-NET-AP7, 1x VX-DSK-M5 + VX-MON-27Q per store |
| Contract renewal due | Bundle the client's next planned purchase into the renewal to lift the discount band |

## Proposal format
Proposal ID (PRP-<client id>-<yyyymmdd>), client, pricing basis (contract id or list/tiers), one line per SKU
(qty, list, discount %, net unit, line total), promotions applied, subtotal, validity date, payment terms, and
up to three cross-sell suggestions as optional lines (not included in the subtotal).
"""

TERMS = f"""# {COMPANY} — General Terms and Conditions of Sale (version 2026.1, effective 2026-01-01)

Applies to every sale unless a signed framework agreement says otherwise; where a framework agreement and these terms
conflict, the framework agreement wins.

1. **Quotations.** Valid for 30 days from issue. Prices in EUR, excluding VAT, delivery included within the EU for
   orders above EUR 1,000 net (EUR 45 flat fee below that).
2. **Orders.** An order is binding once confirmed in writing by {COMPANY}. Stock is allocated at confirmation.
   Orders on hold awaiting a client purchase order keep their allocation for 10 business days, then the allocation is released.
3. **Payment.** Net 30 days from invoice date unless a framework agreement specifies otherwise. Late payments bear
   interest at 8% per year plus a EUR 40 recovery fee. Deliveries may be suspended for accounts more than 30 days overdue.
4. **Delivery.** DAP (Incoterms 2020) to the address on the order. Risk passes on delivery; title passes on full
   payment. Delivery dates are estimates; partial shipments are allowed and invoiced as shipped.
5. **Backorders.** Backordered lines ship automatically when stock arrives, in order-date sequence. The client may
   cancel a backordered line without fee at any time before it ships.
6. **Address changes.** Possible until the order is picked; after picking, a re-routing fee of EUR 75 per shipment applies.
7. **Cancellation.** Free until the order is picked. After picking and before shipment: 10% fee. After shipment,
   cancellation is handled as a return.
8. **Returns.** Unopened products within 30 days of delivery, 15% restocking fee. Opened products are not returnable
   unless defective. End-of-life and custom-configured products are not returnable.
9. **Dead on arrival (DOA).** Reported within 14 days of delivery: free replacement, return label provided.
10. **Warranty.** As stated per product in the product catalogue, from delivery date. Warranty excludes misuse,
    unauthorised modification and consumables. Batteries: 2 years.
11. **Price changes.** List prices may change with 30 days' notice; confirmed orders keep their confirmed prices.
12. **Liability.** Limited to the net value of the affected order; no liability for indirect or consequential loss.
13. **Governing law.** Belgian law; courts of Liège have jurisdiction.
"""


def build_emails_md() -> str:
    out = ["# Client correspondence log (most recent last)\n"]
    for eid, when, frm, to, subj, ticket, body in EMAILS:
        cn = CN[frm]
        out.append(f"\n---\n\n### {eid} · {when} · {C[cn['client']]['name']} ({cn['client']})\n\n"
                   f"- **From:** {cn['name']} <{cn['email']}>\n- **To:** {to}\n- **Subject:** {subj}\n"
                   f"- **Ticket:** {ticket or '—'}\n\n{body}\n")
    return "".join(out)


def build_account_notes_md() -> str:
    out = ["# Account notes (key-account managers)\n"]
    for c in CLIENTS:
        am = ACCOUNT_MANAGERS[c["am"]]
        out.append(f"\n## {c['name']} ({c['id']}) — account manager {am['name']}\n\n")
        out.extend(f"- {n}\n" for n in ACCOUNT_NOTES[c["id"]])
    return "".join(out)


def write_files() -> dict[str, str]:
    orders, lines, reserved = build_orders()
    stock = build_stock(reserved)
    files = {
        "stock-db/stock.csv": _csv(stock),
        "stock-db/stock_movements.csv": _csv([dict(date=d, type=t, sku=s, qty_change_on_hand=q, reference=r, note=n)
                                               for d, t, s, q, r, n in MOVEMENTS]),
        "orders-db/orders.csv": _csv(orders),
        "orders-db/order_lines.csv": _csv(lines),
        "customer-db/clients.csv": _csv([dict(client_id=c["id"], client=c["name"], industry=c["industry"],
                                              country=c["country"], address=c["address"], account_tier=c["tier"],
                                              account_manager=ACCOUNT_MANAGERS[c["am"]]["name"],
                                              account_manager_email=ACCOUNT_MANAGERS[c["am"]]["email"],
                                              customer_since=c["since"], spend_2025_eur=c["spend_2025"],
                                              sites=c["sites"]) for c in CLIENTS]),
        "customer-db/contacts.csv": _csv([dict(contact_id=c["id"], client_id=c["client"],
                                               client=C[c["client"]]["name"], name=c["name"], title=c["title"],
                                               email=c["email"], phone=c["phone"], primary_contact=c["primary"])
                                          for c in CONTACTS]),
        "customer-db/tickets.csv": _csv([dict(ticket_id=t["id"], client_id=t["client"], client=C[t["client"]]["name"],
                                              contact=CN[t["contact"]]["name"], opened=t["opened"], closed=t["closed"],
                                              status=t["status"], priority=t["priority"], channel=t["channel"],
                                              subject=t["subject"], related_order=t["order"], related_sku=t["sku"],
                                              summary=t["summary"]) for t in TICKETS]),
        "customer-db/emails.md": build_emails_md(),
        "customer-db/account_notes.md": build_account_notes_md(),
        "sales-db/price_list.csv": _csv(build_price_list()),
        "sales-db/pricing_policy.md": PRICING_POLICY,
        "contracts-db/contracts.csv": _csv([dict(contract_id=ct["id"], client_id=ct["client"],
                                                 client=C[ct["client"]]["name"], type=ct["type"], start_date=ct["start"],
                                                 end_date=ct["end"], status=ct["status"],
                                                 discount_datacenter_pct=ct["disc"]["Datacenter"],
                                                 discount_networking_pct=ct["disc"]["Networking"],
                                                 discount_endpoint_pct=ct["disc"]["Endpoint"],
                                                 payment_terms=ct["payment"], incoterms=ct["incoterms"],
                                                 service_level=ct["sla"], notice_and_renewal=ct["notice"],
                                                 price_protection=ct["price_protection"],
                                                 special_clauses=ct["special"]) for ct in CONTRACTS]),
        "contracts-db/terms_and_conditions.md": TERMS,
        "products-db/products.md": build_products_md(),
    }
    for rel, text in files.items():
        path = DATA_DIR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return files


def check_consistency(files: dict[str, str]) -> None:
    """Every id referenced anywhere must exist in its owning table."""
    skus, clients = set(P), set(C)
    orders = {o["id"] for o in ORDERS}
    blob = "\n".join(files.values())
    for sku in set(re.findall(r"VX-[A-Z0-9]+-[A-Z0-9]+(?:-[A-Z0-9]+)?", blob)):
        assert sku in skus, f"unknown SKU referenced: {sku}"
    for so in set(re.findall(r"SO-\d{5}", blob)):
        assert so in orders, f"unknown order referenced: {so}"
    for cid in set(re.findall(r"C-\d{4}", blob)):
        assert cid in clients, f"unknown client referenced: {cid}"
    contract_ids = {ct["id"] for ct in CONTRACTS}
    for ref in set(re.findall(r"(?:FA|EA)-\d{4}-\d{3}", blob)):
        assert ref in contract_ids, f"unknown contract referenced: {ref}"
    for t in TICKETS:
        assert not t["order"] or t["order"] in orders and next(o for o in ORDERS if o["id"] == t["order"])["client"] == t["client"]
    for _, _, frm, *_ in EMAILS:
        assert frm in CN


def build_bundle(files: dict[str, str]) -> None:
    template = TEMPLATE.read_text(encoding="utf-8")

    def _inline(m: re.Match[str]) -> str:
        indent, rel = m.group(1), m.group(2)
        body = files[rel].rstrip("\n").split("\n")
        assert all(line == line.rstrip() for line in body), f"trailing whitespace in {rel}"
        return f"{indent}content: |\n" + "\n".join(f"{indent}  {line}" if line else "" for line in body)

    out = re.sub(r"^( *)content: \{\{file:([^}]+)\}\}$", _inline, template, flags=re.M)
    assert "{{file:" not in out
    BUNDLE.write_text(out, encoding="utf-8")


if __name__ == "__main__":
    files = write_files()
    check_consistency(files)
    build_bundle(files)
    print(f"wrote {len(files)} data files under {DATA_DIR.relative_to(ROOT)} and {BUNDLE.relative_to(ROOT)}")
