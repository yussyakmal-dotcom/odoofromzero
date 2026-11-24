"""Pure integer arithmetic for RO-only Packing consolidation.

This phase does not include SO. Kitchen manufacturing is rounded UP to whole
BoM batches. If full demand fits Published Planning Max, the rounding surplus
is distributed prorata to the shops that ordered the SKU. If capacity is short,
the producible whole batches are allocated prorata as shortage against shops'
original RO Qty. Original RO remains unchanged in either case.
"""


def round_production_up(total_requested, bom_output):
    if not isinstance(total_requested, int) or isinstance(total_requested, bool) or total_requested < 0:
        raise ValueError('Total requested must be a nonnegative integer.')
    if not isinstance(bom_output, int) or isinstance(bom_output, bool) or bom_output <= 0:
        raise ValueError('BoM output must be a positive integer.')
    return ((total_requested + bom_output - 1) // bom_output) * bom_output


def allocate_surplus_prorata(requests, bom_output):
    """Return (produced, {store_id: {'requested': int, 'surplus': int, 'allocated': int}}).

    requests: {store_id: requested_int}. Surplus allocated by Hamilton/largest
    remainder, with ties resolved by ascending store ID. A zero-qty store
    receives zero surplus. No float rounding. Store ID must be positive int.
    """
    if not isinstance(requests, dict):
        raise ValueError('Requests must be a dictionary of store ID to Qty.')
    for store_id, qty in requests.items():
        if not isinstance(store_id, int) or isinstance(store_id, bool) or store_id <= 0:
            raise ValueError('Store ID must be a positive integer.')
        if not isinstance(qty, int) or isinstance(qty, bool) or qty < 0:
            raise ValueError('Requested Qty must be a nonnegative integer.')

    total = sum(requests.values())
    produced = round_production_up(total, bom_output)
    surplus = produced - total
    allocations = {
        key: {'requested': qty, 'surplus': 0, 'allocated': qty}
        for key, qty in requests.items()
    }
    if not total or not surplus:
        return produced, allocations

    remainder = []
    distributed = 0
    for store_id, requested in requests.items():
        numerator = surplus * requested
        base = numerator // total
        allocations[store_id]['surplus'] = base
        allocations[store_id]['allocated'] += base
        distributed += base
        remainder.append((numerator % total, store_id))

    # Deterministic Hamilton method: remaining units to biggest fractions,
    # with stable tie-breaker so repeated previews have identical results.
    remainder.sort(key=lambda item: (-item[0], item[1]))
    for _, store_id in remainder[:surplus - distributed]:
        allocations[store_id]['surplus'] += 1
        allocations[store_id]['allocated'] += 1

    assert sum(row['allocated'] for row in allocations.values()) == produced
    return produced, allocations


def allocate_capacity_prorata(requests, bom_output, max_capacity):
    """Preview capacity, then prorate BoM rounding surplus to ordering shops.

    Return (planned_mo_qty, per_store_allocations, capacity_status).
    All store lines satisfy: original RO = final allocation + shortage.

    * If the BoM-rounded MO fits Planning Max, assign full original Qty
      PLUS all BoM rounding surplus to ordering shops via stable Hamilton
      prorata (largest remainder, tie-break ascending store ID).
    * If the BoM-rounded MO would exceed Max, limit the production target
      to whole batches fitting Max and REDUCE each store's allocation
      proportionally using integer Hamilton rounding. Record shortages.
    * If even one batch cannot fit, block instead of creating a zero-Qty MO.

    RO documents remain unchanged. In all cases:
       final store allocation = original RO - shortage + surplus
       sum(store allocations) = planned MO Qty (when total RO demand > 0).
    """
    if not isinstance(requests, dict):
        raise ValueError('Requests must be a dictionary of store ID to Qty.')
    for store_id, qty in requests.items():
        if not isinstance(store_id, int) or isinstance(store_id, bool) or store_id <= 0:
            raise ValueError('Store ID must be a positive integer.')
        if not isinstance(qty, int) or isinstance(qty, bool) or qty < 0:
            raise ValueError('Requested Qty must be a nonnegative integer.')
    if not isinstance(max_capacity, int) or isinstance(max_capacity, bool) or max_capacity < 0:
        raise ValueError('Planning Max must be a nonnegative integer.')
    if not isinstance(bom_output, int) or isinstance(bom_output, bool) or bom_output <= 0:
        raise ValueError('BoM output must be a positive integer.')

    total = sum(requests.values())
    produced = round_production_up(total, bom_output)
    if produced <= max_capacity:
        _, distributed = allocate_surplus_prorata(requests, bom_output)
        return produced, {
            store_id: {
                'requested': row['requested'],
                'surplus': row['surplus'],
                'shortage': 0,
                'allocated': row['allocated'],
            }
            for store_id, row in distributed.items()
        }, 'ok'

    available = (max_capacity // bom_output) * bom_output
    if available <= 0:
        return 0, {
            store_id: {'requested': qty, 'surplus': 0, 'shortage': qty, 'allocated': 0}
            for store_id, qty in requests.items()
        }, 'blocked'

    # Whole BoM batch constraint: available < total whenever rounded > Max.
    if not 0 < available < total:
        raise ValueError('Unexpected capacity calculation for whole BoM batches.')
    result = {}
    remainders = []
    distributed = 0
    for store_id, requested in requests.items():
        numerator = available * requested
        base = numerator // total
        result[store_id] = {
            'requested': requested,
            'surplus': 0,  # No surplus when capacity is insufficient.
            'shortage': requested - base,
            'allocated': base,
        }
        remainders.append((numerator % total, store_id))
        distributed += base

    # Distribute the available STORE ALLOCATION, not any hypothetical surplus.
    # Equal fractional remainders use the smallest store ID.
    remainders.sort(key=lambda item: (-item[0], item[1]))
    for _, store_id in remainders[:available - distributed]:
        result[store_id]['allocated'] += 1
        result[store_id]['shortage'] -= 1

    assert sum(row['allocated'] for row in result.values()) == available
    assert sum(row['shortage'] for row in result.values()) == total - available
    assert all(
        0 <= row['allocated'] <= row['requested']
        and row['allocated'] + row['shortage'] == row['requested']
        and row['surplus'] == 0 for row in result.values()
    )
    return available, result, 'prorated'
