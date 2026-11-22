"""Pure integer arithmetic for RO-only Packing consolidation.

This phase does not include SO. Deterministic largest remainder allocation
ensures the sum of allocated quantities equals the rounded production quantity,
and every requesting store receives at least its original requested amount.
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
    """Return (produced, allocations, status) with explicit store shortage.

    The published Max is a ceiling, and MO must comprise whole BoM batches.
    Standard path: round demand UP and distribute BoM surplus.
    Overcapacity path: round Max DOWN to whole batches, allocate those
    units proportionally by Hamilton, and preserve original RO demand.
    If not even one batch fits, return status 'blocked' with no MO.
    Never alter Confirmed RO Qty or silently lose unfulfilled store demand.
    """
    if not isinstance(max_capacity, int) or isinstance(max_capacity, bool) or max_capacity < 0:
        raise ValueError('Planning Max must be a nonnegative integer.')
    rounded, allocations = allocate_surplus_prorata(requests, bom_output)
    if rounded <= max_capacity:
        return rounded, {
            store_id: dict(values, shortage=0) for store_id, values in allocations.items()
        }, 'ok'

    available = (max_capacity // bom_output) * bom_output
    total = sum(requests.values())
    if available <= 0:
        return 0, {
            store_id: {'requested': qty, 'surplus': 0, 'shortage': qty, 'allocated': 0}
            for store_id, qty in requests.items()
        }, 'blocked'

    # available <= total whenever rounded > max_capacity.
    if available >= total:
        raise ValueError('Unexpected capacity arithmetic: available must be below demand.')

    result = {}
    remainders = []
    distributed = 0
    for store_id, qty in requests.items():
        numerator = available * qty
        base = numerator // total
        result[store_id] = {
            'requested': qty, 'surplus': 0, 'shortage': qty - base,
            'allocated': base,
        }
        remainders.append((numerator % total, store_id))
        distributed += base
    for _, store_id in sorted(remainders, key=lambda item: (-item[0], item[1]))[
            :available - distributed]:
        result[store_id]['allocated'] += 1
        result[store_id]['shortage'] -= 1

    assert sum(row['allocated'] for row in result.values()) == available
    assert sum(row['shortage'] for row in result.values()) == total - available
    assert all(0 <= row['allocated'] <= row['requested'] for row in result.values())
    return available, result, 'prorated'
