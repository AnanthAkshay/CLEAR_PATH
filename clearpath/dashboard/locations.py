"""Human-readable city location and district names for ClearPath grid network.

Provides natural urban landmarks, street intersections, and district names
for all 36 junctions in the microscopic simulation grid.
"""

from __future__ import annotations

from typing import Dict, Optional

INTERSECTION_NAMES: Dict[str, Dict[str, str]] = {
    # Row 0: Harbor & South Shore Boulevard (E-W)
    "j_0_0": {"name": "South Port Gateway", "cross": "1st Ave & Harbor Blvd", "district": "Harbor District"},
    "j_0_1": {"name": "Marina Promenade", "cross": "2nd Ave & Harbor Blvd", "district": "Harbor District"},
    "j_0_2": {"name": "Fisherman's Wharf", "cross": "3rd Ave & Harbor Blvd", "district": "Waterfront"},
    "j_0_3": {"name": "Bayside Transit Terminal", "cross": "4th Ave & Harbor Blvd", "district": "Waterfront"},
    "j_0_4": {"name": "Convention Waterfront", "cross": "5th Ave & Harbor Blvd", "district": "Convention Center"},
    "j_0_5": {"name": "Central Medical Plaza", "cross": "6th Ave & Harbor Blvd", "district": "Central Memorial Hospital"},

    # Row 1: Elm Street (E-W)
    "j_1_0": {"name": "West Market Plaza", "cross": "1st Ave & Elm St", "district": "West Market"},
    "j_1_1": {"name": "Historic Old Town", "cross": "2nd Ave & Elm St", "district": "Old Town"},
    "j_1_2": {"name": "Arts & Theater Quarter", "cross": "3rd Ave & Elm St", "district": "Arts District"},
    "j_1_3": {"name": "Grand Central Square", "cross": "4th Ave & Elm St", "district": "Civic Center"},
    "j_1_4": {"name": "Boutique Row", "cross": "5th Ave & Elm St", "district": "Shopping Quarter"},
    "j_1_5": {"name": "Civic Park South", "cross": "6th Ave & Elm St", "district": "Medical Border"},

    # Row 2: Oak Street & Midtown (E-W)
    "j_2_0": {"name": "West Midtown Gate", "cross": "1st Ave & Oak St", "district": "Midtown West"},
    "j_2_1": {"name": "Bankers Row", "cross": "2nd Ave & Oak St", "district": "Financial District"},
    "j_2_2": {"name": "Riverside Health Plaza", "cross": "3rd Ave & Oak St", "district": "Riverside Urgent Care"},
    "j_2_3": {"name": "Financial Core", "cross": "4th Ave & Oak St", "district": "Financial District"},
    "j_2_4": {"name": "Stock Exchange Square", "cross": "5th Ave & Oak St", "district": "Financial District"},
    "j_2_5": {"name": "East River Overlook", "cross": "6th Ave & Oak St", "district": "East River"},

    # Row 3: Central Broadway (Major Arterial E-W)
    "j_3_0": {"name": "West Coast Highway Hub", "cross": "1st Ave & Broadway", "district": "Highway Interchange"},
    "j_3_1": {"name": "Union Plaza", "cross": "2nd Ave & Broadway", "district": "Downtown"},
    "j_3_2": {"name": "Metropolitan Hall", "cross": "3rd Ave & Broadway", "district": "Civic Center"},
    "j_3_3": {"name": "Downtown Grand Junction", "cross": "4th Ave & Broadway", "district": "Metro Center Hub"},
    "j_3_4": {"name": "Fashion Center", "cross": "5th Ave & Broadway", "district": "Shopping Quarter"},
    "j_3_5": {"name": "Eastside Arterial Crossing", "cross": "6th Ave & Broadway", "district": "East Expressway"},

    # Row 4: Pine Street & University Quarter (E-W)
    "j_4_0": {"name": "Northwest Industrial Park", "cross": "1st Ave & Pine St", "district": "Industrial Quarter"},
    "j_4_1": {"name": "Innovation Campus", "cross": "2nd Ave & Pine St", "district": "Tech Park"},
    "j_4_2": {"name": "University Quadrangle", "cross": "3rd Ave & Pine St", "district": "University District"},
    "j_4_3": {"name": "Science & Research Lab", "cross": "4th Ave & Pine St", "district": "University District"},
    "j_4_4": {"name": "Technology Hub", "cross": "5th Ave & Pine St", "district": "Tech Park"},
    "j_4_5": {"name": "Botanical Gardens", "cross": "6th Ave & Pine St", "district": "Eastside Park"},

    # Row 5: North Parkway & Highland Boulevard (E-W)
    "j_5_0": {"name": "Westside Health Hilltop", "cross": "1st Ave & North Pkwy", "district": "Westside Community Clinic"},
    "j_5_1": {"name": "Highland View Park", "cross": "2nd Ave & North Pkwy", "district": "Highland Heights"},
    "j_5_2": {"name": "Summit Terrace", "cross": "3rd Ave & North Pkwy", "district": "North Terrace"},
    "j_5_3": {"name": "North Metro Terminal", "cross": "4th Ave & North Pkwy", "district": "North Interchange"},
    "j_5_4": {"name": "Forest Ridge Crossing", "cross": "5th Ave & North Pkwy", "district": "Forest Ridge"},
    "j_5_5": {"name": "North General Heights", "cross": "6th Ave & North Pkwy", "district": "North General Hospital"},
}

GRID_NODES = list(INTERSECTION_NAMES.keys())


def get_location_name(node: str) -> str:
    """Return the landmark name of an intersection node."""
    data = INTERSECTION_NAMES.get(node)
    if data:
        return data["name"]
    return node


def get_location_cross(node: str) -> str:
    """Return the street cross-intersection for a node."""
    data = INTERSECTION_NAMES.get(node)
    if data:
        return data["cross"]
    return node


def get_location_display(node: str) -> str:
    """Return a polished UI dropdown string showing landmark name and street crossing."""
    data = INTERSECTION_NAMES.get(node)
    if data:
        return f"{data['name']} ({data['cross']})"
    return node


def get_edge_label(u: str, v: str) -> str:
    """Return a natural road corridor name like 'Union Plaza ➔ Metropolitan Hall'."""
    u_name = get_location_name(u)
    v_name = get_location_name(v)
    return f"{u_name} ➔ {v_name}"


