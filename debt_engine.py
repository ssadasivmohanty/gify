"""
debt_engine.py:
Computes net balances and resolves group debts via greedy two-pointer matching.
"""


def calculate_group_settlements(members: list, splits: list):
    """Calculates net balances and simplified debt repayments.

    Parameters:
        members: list of (id, group_id, name, upi_id) or (id, name, upi_id)
        splits: list of (expense_id, paid_by_member_id, member_id, owed_amount)

    Returns:
        balances: {member_id: net_float}
        settlements: list of dicts [
            {"from_id": int, "from_name": str, "to_id": int, "to_name": str, "amount": float, "to_upi": str}
        ]
    """
    member_map = {}
    balances = {}

    for m in members:
        m_id = m[0]
        # Accommodates 4-item (id, group_id, name, upi) or 3-item (id, name, upi)
        if len(m) >= 4:
            m_name = m[2]
            m_upi = m[3] or ""
        else:
            m_name = m[1]
            m_upi = m[2] or ""
        member_map[m_id] = {"name": m_name, "upi": m_upi}
        balances[m_id] = 0.0

    # Payer receives (+), Debtor owes (-)
    for exp_id, payer_id, debtor_id, owed_amt in splits:
        if payer_id == debtor_id:
            continue

        if payer_id in balances:
            balances[payer_id] += float(owed_amt)
        if debtor_id in balances:
            balances[debtor_id] -= float(owed_amt)

    debtors = []
    creditors = []

    for mem_id, net in balances.items():
        rounded_net = round(net, 2)
        if rounded_net < -0.01:
            debtors.append({"id": mem_id, "amount": -rounded_net})
        elif rounded_net > 0.01:
            creditors.append({"id": mem_id, "amount": rounded_net})

    # Sort descending by debt magnitude
    debtors.sort(key=lambda x: x["amount"], reverse=True)
    creditors.sort(key=lambda x: x["amount"], reverse=True)

    settlements = []
    d_idx = 0
    c_idx = 0

    while d_idx < len(debtors) and c_idx < len(creditors):
        debtor = debtors[d_idx]
        creditor = creditors[c_idx]

        settle_amt = round(min(debtor["amount"], creditor["amount"]), 2)

        if settle_amt > 0.01:
            settlements.append({
                "from_id": debtor["id"],
                "from_name": member_map[debtor["id"]]["name"],
                "to_id": creditor["id"],
                "to_name": member_map[creditor["id"]]["name"],
                "amount": settle_amt,
                "to_upi": member_map[creditor["id"]]["upi"],
            })

        debtor["amount"] = round(debtor["amount"] - settle_amt, 2)
        creditor["amount"] = round(creditor["amount"] - settle_amt, 2)

        if debtor["amount"] <= 0.01:
            d_idx += 1
        if creditor["amount"] <= 0.01:
            c_idx += 1

    return balances, settlements