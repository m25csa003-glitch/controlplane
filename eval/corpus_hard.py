"""Adversarial cases.

The first version of the eval set scored 100% on every case type, which is not
a result - it means the set was too easy for the checker that was tuned on it.
These are the shapes that actually break a grounding check:

  quantifier_flip   "up to X" becomes "at least X". One word, opposite meaning.
  conditional_flip  the condition under which a rule applies is changed.
  partial_truth     one true clause and one invented clause in one sentence.
  hedged_correct    faithful but hedged. Must pass; hedging is not hallucination.
  multi_hop         true only by combining two chunks. Must pass, and per-chunk
                    entailment scoring is structurally bad at it.

(text, should_flag) per entry.
"""

HARD = {
    "pol-1": {
        "quantifier_flip": ("Room rent is capped at no less than 1 percent of sum insured per day.", True),
        "conditional_flip": ("Room rent capping applies only after the first day of admission.", True),
        "partial_truth": ("Room rent capping is 1 percent of sum insured per day, and unused capping carries forward to the next admission.", True),
        "hedged_correct": ("Room rent is generally limited to about 1 percent of the sum insured each day.", False),
    },
    "pol-2": {
        "quantifier_flip": ("Cashless treatment is available at network hospitals and at least some others.", True),
        "conditional_flip": ("Cashless treatment is available at network hospitals once the claim is settled.", True),
        "partial_truth": ("Cashless treatment is available at network hospitals only, and the network covers every district.", True),
        "hedged_correct": ("As a rule, you would need to be at a network hospital for cashless treatment.", False),
    },
    "pol-3": {
        "quantifier_flip": ("The waiting period for pre-existing conditions is at most 36 months from policy inception.", True),
        "conditional_flip": ("Pre-existing conditions are covered within 36 months of policy inception.", True),
        "partial_truth": ("The waiting period is 36 months from inception, and it restarts if you change your plan.", True),
        "hedged_correct": ("Pre-existing conditions typically become payable roughly three years after inception.", False),
    },
    "pol-4": {
        "quantifier_flip": ("Ambulance charges are reimbursed from 2000 rupees per hospitalisation.", True),
        "conditional_flip": ("Ambulance charges are reimbursed up to 2000 rupees per policy year.", True),
        "partial_truth": ("Ambulance charges are reimbursed up to 2000 rupees per hospitalisation, and repeat trips are counted separately.", True),
        "hedged_correct": ("Ambulance costs are covered to a limit of around two thousand rupees each hospitalisation.", False),
    },
    "pol-5": {
        "quantifier_flip": ("Day care procedures require at least 24 hour hospitalisation under Annexure II.", True),
        "conditional_flip": ("Annexure II procedures are covered only where 24 hour hospitalisation occurred.", True),
        "partial_truth": ("Annexure II day care procedures are covered without 24 hour hospitalisation, and the list is updated monthly.", True),
        "hedged_correct": ("Procedures on the Annexure II list generally do not need an overnight stay.", False),
    },
    "hr-1": {
        "quantifier_flip": ("Employees accrue at least 18 days of earned leave per calendar year.", True),
        "conditional_flip": ("Employees accrue 18 days of earned leave per financial year.", True),
        "partial_truth": ("Employees accrue 18 days of earned leave per calendar year, and unused days lapse in December.", True),
        "hedged_correct": ("You build up around eighteen days of earned leave over a year.", False),
    },
    "hr-2": {
        "quantifier_flip": ("Laptop refresh is available after at most 4 years for engineering roles.", True),
        "conditional_flip": ("Laptop refresh is 4 years for all roles.", True),
        "partial_truth": ("Engineering laptops refresh every 4 years, and the old device may be kept by the employee.", True),
        "hedged_correct": ("Engineering hardware is typically replaced on roughly a four year cycle.", False),
    },
    "hr-3": {
        "quantifier_flip": ("Reimbursement claims must be submitted at least 30 days after the expense.", True),
        "conditional_flip": ("Reimbursement claims must be submitted within 30 days of approval.", True),
        "partial_truth": ("Claims must be submitted within 30 days of expense, and finance processes them the same week.", True),
        "hedged_correct": ("You generally have about a month from the expense to file the claim.", False),
    },
    "hr-4": {
        "quantifier_flip": ("Remote work is permitted from 10 days per month with manager approval.", True),
        "conditional_flip": ("Remote work is permitted up to 10 days per month without manager approval.", True),
        "partial_truth": ("Remote work is permitted up to 10 days a month with manager approval, and unused days roll over.", True),
        "hedged_correct": ("With sign-off from your manager you can usually work remotely about ten days a month.", False),
    },
    "hr-5": {
        "quantifier_flip": ("The internal VPN must be used for most access to production systems.", True),
        "conditional_flip": ("The internal VPN must be used for access to production systems from outside the office.", True),
        "partial_truth": ("Production access requires the internal VPN, and VPN sessions time out after eight hours.", True),
        "hedged_correct": ("You would normally need to be on the internal VPN to reach production.", False),
    },
    "cl-1": {
        "quantifier_flip": ("Claims up to 500000 rupees require a second-level adjudicator sign-off.", True),
        "conditional_flip": ("Claims above 500000 rupees require second-level sign-off after settlement.", True),
        "partial_truth": ("Claims above 500000 rupees need second-level sign-off, and the adjudicator has three days to respond.", True),
        "hedged_correct": ("Anything over roughly five lakh generally needs a second adjudicator.", False),
    },
    "cl-2": {
        "quantifier_flip": ("A claim filed within 90 days after discharge is time-barred.", True),
        "conditional_flip": ("A claim filed more than 90 days after admission is time-barred.", True),
        "partial_truth": ("Claims past 90 days from discharge are time-barred, and the limit is waived for inpatient cases.", True),
        "hedged_correct": ("You would usually lose the claim about three months after discharge.", False),
    },
    "cl-3": {
        "quantifier_flip": ("Some fraud indicators require escalation to the investigation unit before settlement.", True),
        "conditional_flip": ("Fraud indicators require escalation to the investigation unit after settlement.", True),
        "partial_truth": ("Fraud indicators go to investigations before settlement, and the member is notified at that point.", True),
        "hedged_correct": ("Where fraud markers show up, the case would normally go to investigations first.", False),
    },
    "cl-4": {
        "quantifier_flip": ("Policy lapses if premium is unpaid for up to 45 days past the grace period.", True),
        "conditional_flip": ("Policy lapses if premium is unpaid for 45 days including the grace period.", True),
        "partial_truth": ("The policy lapses after 45 days past grace, and cover continues for claims incurred earlier.", True),
        "hedged_correct": ("Roughly a month and a half past grace without payment and the policy would lapse.", False),
    },
    "cl-5": {
        "quantifier_flip": ("Co-payment of at least 20 percent applies to members above age 60.", True),
        "conditional_flip": ("Co-payment of 20 percent applies to insured members below age 60.", True),
        "partial_truth": ("Members above 60 carry a 20 percent co-payment, and it is capped at 50000 rupees a year.", True),
        "hedged_correct": ("Members past sixty generally bear about a fifth of the claim themselves.", False),
    },
}

# True only by putting two chunks together. Must pass. Scoring each claim
# against each chunk separately - which is what stops long concatenated
# premises from wrecking entailment - is structurally weak here, so these are
# in the set to keep that tradeoff measured rather than assumed.
MULTI_HOP = {
    "customer_support": [
        ("Cashless treatment at a network hospital is still subject to the 1 percent daily room rent cap.", ["pol-1", "pol-2"]),
        ("A day care procedure at a network hospital can be settled cashless without a 24 hour stay.", ["pol-2", "pol-5"]),
        ("Ambulance reimbursement of up to 2000 rupees applies even where the treatment was a day care procedure.", ["pol-4", "pol-5"]),
    ],
    "internal_copilot": [
        ("An engineer working remotely still needs the internal VPN to reach production systems.", ["hr-4", "hr-5"]),
        ("If you buy a laptop accessory yourself, the 30 day reimbursement window applies.", ["hr-2", "hr-3"]),
        ("You can take earned leave and work remotely in the same month, within the 10 day remote limit.", ["hr-1", "hr-4"]),
    ],
    "decision_support": [
        ("A claim over 500000 rupees filed within 90 days of discharge still needs second-level sign-off.", ["cl-1", "cl-2"]),
        ("A flagged high-value claim goes to investigations before the second-level adjudicator settles it.", ["cl-1", "cl-3"]),
        ("A member over 60 with a lapsed policy has no cover, co-payment notwithstanding.", ["cl-4", "cl-5"]),
    ],
}

# Digit forms the sources use, written out. Same meaning, so these must pass -
# and a checker that matches on numerals will call every one of them a
# fabrication.
NUMERALS = {
    "1": "one", "4": "four", "10": "ten", "18": "eighteen", "20": "twenty",
    "24": "twenty-four", "30": "thirty", "36": "thirty-six", "45": "forty-five",
    "60": "sixty", "90": "ninety", "2000": "two thousand",
    "500000": "five hundred thousand",
}

# Same figure, different unit. Must flag.
UNITS = [
    ("rupees", "dollars"), ("months", "weeks"), ("days", "hours"),
    ("percent", "basis points"),
]
