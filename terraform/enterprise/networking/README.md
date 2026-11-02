# Centralized networking reference

`core/` is a separate Network-account state boundary. It owns the Transit Gateway, route tables, cross-account attachment acceptance, associations, RAM share, VPN, Gateway Load Balancer, and endpoint service. `workload-attachment/` is a per-account boundary that owns only the workload VPC attachment and explicitly approved VPC routes.

The staged handoff is: apply Network core with no workload attachments; share the TGW; create the attachment in the Workload-account state; pass its ID, environment, and CIDR through the reviewed Network-state inputs; then let the Network state accept and associate it. Neither state reads the other's remote state. Promotion inputs must come from reviewed outputs or an approved configuration registry.

No default workload or TGW route is created. `approved_routes`, `inspection_routes`, and `inspection_return_routes` default to empty and must contain explicit prefixes. Direct VPN propagation also defaults to empty; enabling `direct_hybrid_route_environments` creates deliberately uninspected hybrid connectivity and must not be described as inspected.

The GWLB and endpoint service are control-plane examples only. Allowed endpoint consumers must be explicit IAM account-root, role, or user ARNs; Organizations ARNs are unsupported. Endpoint acceptance, GWLB endpoint creation, endpoint route-table steering, appliance instances, target registration, NAT/egress, and symmetric return-path routing are not implemented. Until those resources and healthy appliances exist, keep `inspection_routes` empty. This reference does not provide end-to-end inspection or IDS/IPS.

External prerequisites include the Network and Workload accounts/roles, Organizations-enabled RAM, non-overlapping CIDRs, inspection VPC subnets in at least two Availability Zones, valid customer-gateway/BGP values, and a reviewed failure-domain design. Test attachment rejection, appliance loss, endpoint loss, tunnel loss, and Availability Zone loss before promoting routes.
