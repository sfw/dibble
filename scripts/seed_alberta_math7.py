#!/usr/bin/env python3
"""Seed script: Alberta Mathematics Grade 7 curriculum.

Loads the Alberta K-9 Mathematics curriculum (Grade 7) into Dibble's
runtime tables via the existing PUT API endpoints.

Source: Alberta Education — Programs of Study — Mathematics K-9, Grade 7
https://curriculum.learnalberta.ca/curriculum/en/pos/MAT_79/MATH7

Usage:
    python scripts/seed_alberta_math7.py [--base-url http://localhost:8000] [--api-key KEY]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Alberta Math 7 curriculum data
#
# Structure mirrors Alberta's Programs of Study:
#   Course
#     └── Organizing Idea (OI) — strand-level theme
#           └── Learning Outcome (LO) — assessable objective
#                 └── Knowledge Component (KC) — atomic skill Dibble tracks
#
# KC prerequisite relationships encode the dependency graph that the
# progression and remediation services walk.
# ---------------------------------------------------------------------------

COURSE = {
    "course_id": "ab-math-7",
    "title": "Mathematics Grade 7",
    "subject": "mathematics",
    "grade_band": "7",
    "tags": ["alberta", "k-9", "2022-curriculum"],
}

# -- Organizing ideas -------------------------------------------------------
# Alberta Math 7 has four organizing ideas:
#   1. Number (whole numbers, integers, decimals, fractions, percents)
#   2. Patterns and Relations (expressions, equations, linear relations)
#   3. Shape and Space (measurement, geometry, transformations)
#   4. Statistics and Probability (data, chance)


@dataclass
class KC:
    kc_id: str
    name: str
    outcome_id: str
    difficulty: float = 0.5
    estimated_time_minutes: int = 15
    prerequisite_kc_ids: list[str] = field(default_factory=list)
    nearby_kc_ids: list[str] = field(default_factory=list)
    taxonomy_cluster_id: str | None = None
    concept_family: str | None = None
    tags: list[str] = field(default_factory=list)
    misconceptions: list[dict] = field(default_factory=list)


@dataclass
class Outcome:
    outcome_id: str
    title: str
    description: str
    strand_id: str  # organizing idea strand this belongs to
    kcs: list[KC] = field(default_factory=list)


# -- Strands (one per organizing idea) ----------------------------------------

STRANDS = [
    {
        "strand_id": "ab-m7-oi-number",
        "course_id": "ab-math-7",
        "title": "Number",
        "description": "Whole numbers, integers, decimals, fractions, and percents.",
        "sort_order": 0,
        "tags": ["alberta", "number"],
    },
    {
        "strand_id": "ab-m7-oi-patterns-relations",
        "course_id": "ab-math-7",
        "title": "Patterns and Relations",
        "description": "Expressions, equations, and linear relations.",
        "sort_order": 1,
        "tags": ["alberta", "patterns-relations"],
    },
    {
        "strand_id": "ab-m7-oi-shape-space",
        "course_id": "ab-math-7",
        "title": "Shape and Space",
        "description": "Measurement, geometry, and transformations.",
        "sort_order": 2,
        "tags": ["alberta", "shape-space"],
    },
    {
        "strand_id": "ab-m7-oi-statistics-probability",
        "course_id": "ab-math-7",
        "title": "Statistics and Probability",
        "description": "Data collection, analysis, and chance.",
        "sort_order": 3,
        "tags": ["alberta", "statistics-probability"],
    },
]

# Map organizing idea tags to strand IDs
OI_TO_STRAND = {
    "number": "ab-m7-oi-number",
    "patterns-relations": "ab-m7-oi-patterns-relations",
    "shape-space": "ab-m7-oi-shape-space",
    "statistics-probability": "ab-m7-oi-statistics-probability",
}


# === ORGANIZING IDEA 1: NUMBER =============================================

lo_number: list[Outcome] = [
    # --- LO 1: Decimal operations ---
    Outcome(
        outcome_id="ab-m7-lo-decimal-ops",
        title="Decimal Operations",
        description=(
            "Students develop fluency with operations on decimals, including "
            "addition, subtraction, multiplication, and division. They apply "
            "estimation strategies to predict and verify reasonableness of "
            "results, and solve problems in context."
        ),
        strand_id="ab-m7-oi-number",
        kcs=[
            KC(
                kc_id="ab-m7-kc-decimal-add-sub",
                name="Add and subtract decimals",
                outcome_id="ab-m7-lo-decimal-ops",
                difficulty=0.3,
                estimated_time_minutes=15,
                taxonomy_cluster_id="number-operations",
                concept_family="decimal-arithmetic",
                tags=["decimals", "addition", "subtraction"],
                misconceptions=[
                    {
                        "misconception_id": "mc-decimal-align",
                        "label": "Misaligned decimal points",
                        "description": "Student adds/subtracts without aligning decimal points, treating digits by position from left rather than by place value.",
                        "trigger_terms": ["line up", "align", "place value"],
                        "prerequisite_kc_ids": [],
                        "remediation_hint": "Use grid paper to align place-value columns before computing.",
                    }
                ],
            ),
            KC(
                kc_id="ab-m7-kc-decimal-mult",
                name="Multiply decimals",
                outcome_id="ab-m7-lo-decimal-ops",
                difficulty=0.45,
                estimated_time_minutes=20,
                prerequisite_kc_ids=["ab-m7-kc-decimal-add-sub"],
                taxonomy_cluster_id="number-operations",
                concept_family="decimal-arithmetic",
                tags=["decimals", "multiplication"],
                misconceptions=[
                    {
                        "misconception_id": "mc-decimal-mult-dp",
                        "label": "Wrong decimal-point placement in product",
                        "description": "Student multiplies correctly but places the decimal point incorrectly, often by counting digits from the left instead of total decimal places in the factors.",
                        "trigger_terms": ["decimal places", "product", "point"],
                        "prerequisite_kc_ids": [],
                        "remediation_hint": "Estimate the product first, then count total decimal places in both factors.",
                    }
                ],
            ),
            KC(
                kc_id="ab-m7-kc-decimal-div",
                name="Divide decimals",
                outcome_id="ab-m7-lo-decimal-ops",
                difficulty=0.55,
                estimated_time_minutes=20,
                prerequisite_kc_ids=[
                    "ab-m7-kc-decimal-add-sub",
                    "ab-m7-kc-decimal-mult",
                ],
                taxonomy_cluster_id="number-operations",
                concept_family="decimal-arithmetic",
                tags=["decimals", "division"],
            ),
            KC(
                kc_id="ab-m7-kc-decimal-estimation",
                name="Estimate decimal computations",
                outcome_id="ab-m7-lo-decimal-ops",
                difficulty=0.35,
                estimated_time_minutes=10,
                taxonomy_cluster_id="number-operations",
                concept_family="estimation",
                tags=["decimals", "estimation", "reasonableness"],
            ),
        ],
    ),
    # --- LO 2: Fraction operations ---
    Outcome(
        outcome_id="ab-m7-lo-fraction-ops",
        title="Fraction Operations",
        description=(
            "Students add, subtract, multiply, and divide positive fractions "
            "and mixed numbers. They model operations concretely and "
            "pictorially, connect to symbolic procedures, and solve "
            "problems involving fractions in everyday and mathematical contexts."
        ),
        strand_id="ab-m7-oi-number",
        kcs=[
            KC(
                kc_id="ab-m7-kc-frac-add-sub",
                name="Add and subtract fractions and mixed numbers",
                outcome_id="ab-m7-lo-fraction-ops",
                difficulty=0.5,
                estimated_time_minutes=20,
                taxonomy_cluster_id="number-operations",
                concept_family="fraction-arithmetic",
                tags=["fractions", "addition", "subtraction", "mixed-numbers"],
                misconceptions=[
                    {
                        "misconception_id": "mc-frac-add-denom",
                        "label": "Adding denominators",
                        "description": "Student adds numerators AND denominators (e.g., 1/3 + 1/4 = 2/7) instead of finding a common denominator.",
                        "trigger_terms": ["common denominator", "LCD"],
                        "prerequisite_kc_ids": [],
                        "remediation_hint": "Model with fraction strips to show why denominators must be the same before adding.",
                    }
                ],
            ),
            KC(
                kc_id="ab-m7-kc-frac-mult",
                name="Multiply fractions and mixed numbers",
                outcome_id="ab-m7-lo-fraction-ops",
                difficulty=0.5,
                estimated_time_minutes=20,
                prerequisite_kc_ids=["ab-m7-kc-frac-add-sub"],
                taxonomy_cluster_id="number-operations",
                concept_family="fraction-arithmetic",
                tags=["fractions", "multiplication"],
            ),
            KC(
                kc_id="ab-m7-kc-frac-div",
                name="Divide fractions and mixed numbers",
                outcome_id="ab-m7-lo-fraction-ops",
                difficulty=0.6,
                estimated_time_minutes=20,
                prerequisite_kc_ids=[
                    "ab-m7-kc-frac-add-sub",
                    "ab-m7-kc-frac-mult",
                ],
                taxonomy_cluster_id="number-operations",
                concept_family="fraction-arithmetic",
                tags=["fractions", "division"],
                misconceptions=[
                    {
                        "misconception_id": "mc-frac-div-flip",
                        "label": "Flipping the wrong fraction",
                        "description": "Student inverts the dividend instead of the divisor when dividing fractions.",
                        "trigger_terms": ["reciprocal", "invert", "flip"],
                        "prerequisite_kc_ids": [],
                        "remediation_hint": "Emphasize 'keep-change-flip': keep the first fraction, change ÷ to ×, flip the second.",
                    }
                ],
            ),
        ],
    ),
    # --- LO 3: Integers ---
    Outcome(
        outcome_id="ab-m7-lo-integers",
        title="Integer Operations",
        description=(
            "Students represent, compare, and order integers. They add, "
            "subtract, multiply, and divide integers using concrete, "
            "pictorial, and symbolic representations, and apply integer "
            "operations to solve problems."
        ),
        strand_id="ab-m7-oi-number",
        kcs=[
            KC(
                kc_id="ab-m7-kc-int-represent",
                name="Represent and order integers",
                outcome_id="ab-m7-lo-integers",
                difficulty=0.3,
                estimated_time_minutes=10,
                taxonomy_cluster_id="number-integers",
                concept_family="integers",
                tags=["integers", "number-line", "ordering"],
            ),
            KC(
                kc_id="ab-m7-kc-int-add-sub",
                name="Add and subtract integers",
                outcome_id="ab-m7-lo-integers",
                difficulty=0.5,
                estimated_time_minutes=20,
                prerequisite_kc_ids=["ab-m7-kc-int-represent"],
                taxonomy_cluster_id="number-integers",
                concept_family="integers",
                tags=["integers", "addition", "subtraction"],
                misconceptions=[
                    {
                        "misconception_id": "mc-int-sub-sign",
                        "label": "Sign errors in integer subtraction",
                        "description": "Student treats subtraction of a negative as subtraction rather than addition (e.g., 5 − (−3) = 2 instead of 8).",
                        "trigger_terms": ["double negative", "subtracting negative"],
                        "prerequisite_kc_ids": [],
                        "remediation_hint": "Use number-line hops: subtracting a negative means hopping right.",
                    }
                ],
            ),
            KC(
                kc_id="ab-m7-kc-int-mult-div",
                name="Multiply and divide integers",
                outcome_id="ab-m7-lo-integers",
                difficulty=0.55,
                estimated_time_minutes=20,
                prerequisite_kc_ids=[
                    "ab-m7-kc-int-represent",
                    "ab-m7-kc-int-add-sub",
                ],
                taxonomy_cluster_id="number-integers",
                concept_family="integers",
                tags=["integers", "multiplication", "division"],
                misconceptions=[
                    {
                        "misconception_id": "mc-int-sign-rules",
                        "label": "Confused sign rules for products/quotients",
                        "description": "Student misapplies sign rules, e.g., believes negative × negative = negative.",
                        "trigger_terms": ["sign rule", "negative times negative"],
                        "prerequisite_kc_ids": [],
                        "remediation_hint": "Build a pattern table: (+)(+), (+)(−), (−)(+), (−)(−) to discover the sign rule.",
                    }
                ],
            ),
        ],
    ),
    # --- LO 4: Percent, ratio, rate ---
    Outcome(
        outcome_id="ab-m7-lo-percent-ratio",
        title="Percent, Ratio, and Rate",
        description=(
            "Students understand and apply percent, ratio, and rate. They "
            "solve problems involving percent of a number, fractional "
            "percents, and percents greater than 100%. They express rates "
            "as unit rates and use proportional reasoning."
        ),
        strand_id="ab-m7-oi-number",
        kcs=[
            KC(
                kc_id="ab-m7-kc-percent-of",
                name="Calculate percent of a number",
                outcome_id="ab-m7-lo-percent-ratio",
                difficulty=0.4,
                estimated_time_minutes=15,
                prerequisite_kc_ids=["ab-m7-kc-decimal-mult"],
                taxonomy_cluster_id="number-proportional",
                concept_family="percent",
                tags=["percent", "proportional-reasoning"],
            ),
            KC(
                kc_id="ab-m7-kc-percent-convert",
                name="Convert among fractions, decimals, and percents",
                outcome_id="ab-m7-lo-percent-ratio",
                difficulty=0.4,
                estimated_time_minutes=15,
                prerequisite_kc_ids=[
                    "ab-m7-kc-decimal-add-sub",
                    "ab-m7-kc-frac-add-sub",
                ],
                taxonomy_cluster_id="number-proportional",
                concept_family="percent",
                tags=["percent", "fractions", "decimals", "conversion"],
            ),
            KC(
                kc_id="ab-m7-kc-ratio-rate",
                name="Express and compare ratios and unit rates",
                outcome_id="ab-m7-lo-percent-ratio",
                difficulty=0.5,
                estimated_time_minutes=20,
                prerequisite_kc_ids=["ab-m7-kc-frac-add-sub"],
                taxonomy_cluster_id="number-proportional",
                concept_family="ratio",
                tags=["ratio", "rate", "unit-rate", "proportional-reasoning"],
            ),
            KC(
                kc_id="ab-m7-kc-proportional-reasoning",
                name="Solve proportional reasoning problems",
                outcome_id="ab-m7-lo-percent-ratio",
                difficulty=0.6,
                estimated_time_minutes=25,
                prerequisite_kc_ids=[
                    "ab-m7-kc-percent-of",
                    "ab-m7-kc-ratio-rate",
                ],
                taxonomy_cluster_id="number-proportional",
                concept_family="ratio",
                tags=["proportion", "proportional-reasoning", "problem-solving"],
            ),
        ],
    ),
]

# === ORGANIZING IDEA 2: PATTERNS AND RELATIONS =============================

lo_patterns: list[Outcome] = [
    # --- LO 5: Expressions and equations ---
    Outcome(
        outcome_id="ab-m7-lo-expressions-equations",
        title="Expressions and Equations",
        description=(
            "Students write, evaluate, and simplify algebraic expressions. "
            "They model and solve one-step and two-step linear equations "
            "using concrete materials, pictorial representations, and "
            "symbolic strategies, and verify solutions."
        ),
        strand_id="ab-m7-oi-patterns-relations",
        kcs=[
            KC(
                kc_id="ab-m7-kc-eval-expressions",
                name="Evaluate algebraic expressions",
                outcome_id="ab-m7-lo-expressions-equations",
                difficulty=0.4,
                estimated_time_minutes=15,
                prerequisite_kc_ids=["ab-m7-kc-int-add-sub"],
                taxonomy_cluster_id="algebra-expressions",
                concept_family="expressions",
                tags=["algebra", "expressions", "substitution"],
            ),
            KC(
                kc_id="ab-m7-kc-simplify-expressions",
                name="Simplify algebraic expressions by combining like terms",
                outcome_id="ab-m7-lo-expressions-equations",
                difficulty=0.5,
                estimated_time_minutes=15,
                prerequisite_kc_ids=["ab-m7-kc-eval-expressions"],
                taxonomy_cluster_id="algebra-expressions",
                concept_family="expressions",
                tags=["algebra", "like-terms", "simplify"],
                misconceptions=[
                    {
                        "misconception_id": "mc-like-terms",
                        "label": "Combining unlike terms",
                        "description": "Student combines terms with different variables or exponents (e.g., 3x + 2y = 5xy).",
                        "trigger_terms": ["like terms", "combine"],
                        "prerequisite_kc_ids": [],
                        "remediation_hint": "Sort terms by variable part first, then combine only terms with identical variable parts.",
                    }
                ],
            ),
            KC(
                kc_id="ab-m7-kc-one-step-eq",
                name="Solve one-step linear equations",
                outcome_id="ab-m7-lo-expressions-equations",
                difficulty=0.45,
                estimated_time_minutes=15,
                prerequisite_kc_ids=[
                    "ab-m7-kc-eval-expressions",
                    "ab-m7-kc-int-add-sub",
                ],
                taxonomy_cluster_id="algebra-equations",
                concept_family="equations",
                tags=["algebra", "equations", "one-step"],
            ),
            KC(
                kc_id="ab-m7-kc-two-step-eq",
                name="Solve two-step linear equations",
                outcome_id="ab-m7-lo-expressions-equations",
                difficulty=0.6,
                estimated_time_minutes=20,
                prerequisite_kc_ids=[
                    "ab-m7-kc-one-step-eq",
                    "ab-m7-kc-simplify-expressions",
                ],
                taxonomy_cluster_id="algebra-equations",
                concept_family="equations",
                tags=["algebra", "equations", "two-step"],
            ),
        ],
    ),
    # --- LO 6: Linear relations ---
    Outcome(
        outcome_id="ab-m7-lo-linear-relations",
        title="Linear Relations",
        description=(
            "Students represent linear relations using tables of values, "
            "graphs, and equations. They identify and describe patterns "
            "in tables and graphs, and connect multiple representations "
            "of the same relation."
        ),
        strand_id="ab-m7-oi-patterns-relations",
        kcs=[
            KC(
                kc_id="ab-m7-kc-table-of-values",
                name="Create and interpret tables of values for linear relations",
                outcome_id="ab-m7-lo-linear-relations",
                difficulty=0.4,
                estimated_time_minutes=15,
                prerequisite_kc_ids=["ab-m7-kc-eval-expressions"],
                taxonomy_cluster_id="algebra-relations",
                concept_family="linear-relations",
                tags=["linear", "table-of-values", "patterns"],
            ),
            KC(
                kc_id="ab-m7-kc-graph-linear",
                name="Graph linear relations from tables and equations",
                outcome_id="ab-m7-lo-linear-relations",
                difficulty=0.5,
                estimated_time_minutes=20,
                prerequisite_kc_ids=["ab-m7-kc-table-of-values"],
                taxonomy_cluster_id="algebra-relations",
                concept_family="linear-relations",
                tags=["linear", "graphing", "coordinate-plane"],
            ),
            KC(
                kc_id="ab-m7-kc-connect-representations",
                name="Connect table, graph, and equation representations",
                outcome_id="ab-m7-lo-linear-relations",
                difficulty=0.6,
                estimated_time_minutes=20,
                prerequisite_kc_ids=[
                    "ab-m7-kc-graph-linear",
                    "ab-m7-kc-two-step-eq",
                ],
                taxonomy_cluster_id="algebra-relations",
                concept_family="linear-relations",
                tags=["linear", "multiple-representations"],
            ),
        ],
    ),
]

# === ORGANIZING IDEA 3: SHAPE AND SPACE ====================================

lo_shape: list[Outcome] = [
    # --- LO 7: Circles ---
    Outcome(
        outcome_id="ab-m7-lo-circles",
        title="Circles: Circumference and Area",
        description=(
            "Students explore the relationship between diameter and "
            "circumference (pi). They develop and apply formulas for "
            "circumference and area of circles, and solve related problems."
        ),
        strand_id="ab-m7-oi-shape-space",
        kcs=[
            KC(
                kc_id="ab-m7-kc-circle-circumference",
                name="Calculate circumference of a circle",
                outcome_id="ab-m7-lo-circles",
                difficulty=0.4,
                estimated_time_minutes=15,
                prerequisite_kc_ids=["ab-m7-kc-decimal-mult"],
                taxonomy_cluster_id="geometry-measurement",
                concept_family="circles",
                tags=["circles", "circumference", "pi", "measurement"],
            ),
            KC(
                kc_id="ab-m7-kc-circle-area",
                name="Calculate area of a circle",
                outcome_id="ab-m7-lo-circles",
                difficulty=0.5,
                estimated_time_minutes=15,
                prerequisite_kc_ids=["ab-m7-kc-circle-circumference"],
                taxonomy_cluster_id="geometry-measurement",
                concept_family="circles",
                tags=["circles", "area", "pi", "measurement"],
                misconceptions=[
                    {
                        "misconception_id": "mc-circle-area-formula",
                        "label": "Confusing circumference and area formulas",
                        "description": "Student uses 2πr (circumference) when area (πr²) is needed, or vice versa.",
                        "trigger_terms": ["pi r squared", "2 pi r", "formula"],
                        "prerequisite_kc_ids": [],
                        "remediation_hint": "Circumference is a length (one dimension, 2πr), area is a surface (two dimensions, πr²). Connect to units: cm vs cm².",
                    }
                ],
            ),
        ],
    ),
    # --- LO 8: Area of composite shapes ---
    Outcome(
        outcome_id="ab-m7-lo-area-composite",
        title="Area of Triangles, Parallelograms, and Composite Shapes",
        description=(
            "Students develop and apply formulas for the area of triangles "
            "and parallelograms. They decompose composite 2-D shapes and "
            "calculate total area."
        ),
        strand_id="ab-m7-oi-shape-space",
        kcs=[
            KC(
                kc_id="ab-m7-kc-area-triangle",
                name="Calculate area of a triangle",
                outcome_id="ab-m7-lo-area-composite",
                difficulty=0.4,
                estimated_time_minutes=15,
                taxonomy_cluster_id="geometry-measurement",
                concept_family="area",
                tags=["area", "triangle", "measurement"],
            ),
            KC(
                kc_id="ab-m7-kc-area-parallelogram",
                name="Calculate area of a parallelogram",
                outcome_id="ab-m7-lo-area-composite",
                difficulty=0.4,
                estimated_time_minutes=15,
                nearby_kc_ids=["ab-m7-kc-area-triangle"],
                taxonomy_cluster_id="geometry-measurement",
                concept_family="area",
                tags=["area", "parallelogram", "measurement"],
            ),
            KC(
                kc_id="ab-m7-kc-area-composite",
                name="Calculate area of composite 2-D shapes",
                outcome_id="ab-m7-lo-area-composite",
                difficulty=0.6,
                estimated_time_minutes=20,
                prerequisite_kc_ids=[
                    "ab-m7-kc-area-triangle",
                    "ab-m7-kc-area-parallelogram",
                    "ab-m7-kc-circle-area",
                ],
                taxonomy_cluster_id="geometry-measurement",
                concept_family="area",
                tags=["area", "composite-shapes", "decomposition"],
            ),
        ],
    ),
    # --- LO 9: Transformations ---
    Outcome(
        outcome_id="ab-m7-lo-transformations",
        title="Transformations",
        description=(
            "Students perform and describe transformations (translations, "
            "reflections, rotations) on the coordinate plane. They identify "
            "the image of a shape after single and combined transformations."
        ),
        strand_id="ab-m7-oi-shape-space",
        kcs=[
            KC(
                kc_id="ab-m7-kc-translations",
                name="Perform and describe translations on a coordinate plane",
                outcome_id="ab-m7-lo-transformations",
                difficulty=0.35,
                estimated_time_minutes=15,
                prerequisite_kc_ids=["ab-m7-kc-graph-linear"],
                taxonomy_cluster_id="geometry-transformations",
                concept_family="transformations",
                tags=["transformations", "translations", "coordinate-plane"],
            ),
            KC(
                kc_id="ab-m7-kc-reflections",
                name="Perform and describe reflections on a coordinate plane",
                outcome_id="ab-m7-lo-transformations",
                difficulty=0.4,
                estimated_time_minutes=15,
                prerequisite_kc_ids=["ab-m7-kc-graph-linear"],
                nearby_kc_ids=["ab-m7-kc-translations"],
                taxonomy_cluster_id="geometry-transformations",
                concept_family="transformations",
                tags=["transformations", "reflections", "coordinate-plane"],
            ),
            KC(
                kc_id="ab-m7-kc-rotations",
                name="Perform and describe rotations on a coordinate plane",
                outcome_id="ab-m7-lo-transformations",
                difficulty=0.5,
                estimated_time_minutes=15,
                prerequisite_kc_ids=["ab-m7-kc-graph-linear"],
                nearby_kc_ids=[
                    "ab-m7-kc-translations",
                    "ab-m7-kc-reflections",
                ],
                taxonomy_cluster_id="geometry-transformations",
                concept_family="transformations",
                tags=["transformations", "rotations", "coordinate-plane"],
            ),
            KC(
                kc_id="ab-m7-kc-combined-transforms",
                name="Describe combined transformations",
                outcome_id="ab-m7-lo-transformations",
                difficulty=0.6,
                estimated_time_minutes=20,
                prerequisite_kc_ids=[
                    "ab-m7-kc-translations",
                    "ab-m7-kc-reflections",
                    "ab-m7-kc-rotations",
                ],
                taxonomy_cluster_id="geometry-transformations",
                concept_family="transformations",
                tags=["transformations", "combined", "composition"],
            ),
        ],
    ),
]

# === ORGANIZING IDEA 4: STATISTICS AND PROBABILITY =========================

lo_stats: list[Outcome] = [
    # --- LO 10: Data collection and display ---
    Outcome(
        outcome_id="ab-m7-lo-data",
        title="Data Collection, Display, and Analysis",
        description=(
            "Students formulate questions, collect first-hand and second-hand "
            "data, and organize data using frequency tables and stem-and-leaf "
            "plots. They determine measures of central tendency (mean, "
            "median, mode) and use them to analyze data and draw conclusions."
        ),
        strand_id="ab-m7-oi-statistics-probability",
        kcs=[
            KC(
                kc_id="ab-m7-kc-central-tendency",
                name="Determine mean, median, and mode",
                outcome_id="ab-m7-lo-data",
                difficulty=0.35,
                estimated_time_minutes=15,
                prerequisite_kc_ids=[
                    "ab-m7-kc-decimal-add-sub",
                    "ab-m7-kc-decimal-div",
                ],
                taxonomy_cluster_id="statistics",
                concept_family="central-tendency",
                tags=["statistics", "mean", "median", "mode"],
                misconceptions=[
                    {
                        "misconception_id": "mc-mean-median",
                        "label": "Confusing mean and median",
                        "description": "Student calculates the mean when asked for the median, or vice versa.",
                        "trigger_terms": ["average", "middle"],
                        "prerequisite_kc_ids": [],
                        "remediation_hint": "Mean = sum ÷ count (the balance point). Median = middle value when ordered. Practice identifying which is asked for.",
                    }
                ],
            ),
            KC(
                kc_id="ab-m7-kc-data-display",
                name="Create and interpret graphs and plots",
                outcome_id="ab-m7-lo-data",
                difficulty=0.4,
                estimated_time_minutes=20,
                prerequisite_kc_ids=["ab-m7-kc-central-tendency"],
                taxonomy_cluster_id="statistics",
                concept_family="data-display",
                tags=["statistics", "graphs", "stem-and-leaf", "circle-graph"],
            ),
            KC(
                kc_id="ab-m7-kc-data-analysis",
                name="Analyze data to draw conclusions and identify bias",
                outcome_id="ab-m7-lo-data",
                difficulty=0.55,
                estimated_time_minutes=20,
                prerequisite_kc_ids=[
                    "ab-m7-kc-central-tendency",
                    "ab-m7-kc-data-display",
                ],
                taxonomy_cluster_id="statistics",
                concept_family="data-analysis",
                tags=["statistics", "analysis", "bias", "conclusions"],
            ),
        ],
    ),
    # --- LO 11: Probability ---
    Outcome(
        outcome_id="ab-m7-lo-probability",
        title="Probability",
        description=(
            "Students express probabilities as fractions, decimals, and "
            "percents. They compare experimental and theoretical "
            "probability, determine the probability of independent events, "
            "and conduct probability experiments."
        ),
        strand_id="ab-m7-oi-statistics-probability",
        kcs=[
            KC(
                kc_id="ab-m7-kc-theoretical-prob",
                name="Determine theoretical probability",
                outcome_id="ab-m7-lo-probability",
                difficulty=0.4,
                estimated_time_minutes=15,
                prerequisite_kc_ids=[
                    "ab-m7-kc-frac-add-sub",
                    "ab-m7-kc-percent-convert",
                ],
                taxonomy_cluster_id="probability",
                concept_family="probability",
                tags=["probability", "theoretical", "fractions"],
            ),
            KC(
                kc_id="ab-m7-kc-experimental-prob",
                name="Conduct experiments and compare to theoretical probability",
                outcome_id="ab-m7-lo-probability",
                difficulty=0.5,
                estimated_time_minutes=20,
                prerequisite_kc_ids=["ab-m7-kc-theoretical-prob"],
                taxonomy_cluster_id="probability",
                concept_family="probability",
                tags=["probability", "experimental", "comparison"],
            ),
            KC(
                kc_id="ab-m7-kc-independent-events",
                name="Determine probability of independent events",
                outcome_id="ab-m7-lo-probability",
                difficulty=0.6,
                estimated_time_minutes=20,
                prerequisite_kc_ids=[
                    "ab-m7-kc-theoretical-prob",
                    "ab-m7-kc-frac-mult",
                ],
                taxonomy_cluster_id="probability",
                concept_family="probability",
                tags=["probability", "independent-events", "compound"],
            ),
        ],
    ),
]

# Combine all outcomes
ALL_OUTCOMES: list[Outcome] = lo_number + lo_patterns + lo_shape + lo_stats

# Map strand IDs to human-readable names
STRAND_LABELS = {
    "ab-m7-oi-number": "Number",
    "ab-m7-oi-patterns-relations": "Patterns and Relations",
    "ab-m7-oi-shape-space": "Shape and Space",
    "ab-m7-oi-statistics-probability": "Statistics and Probability",
}


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------


def seed(base_url: str, api_key: str | None) -> None:
    import httpx

    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    with httpx.Client(base_url=base_url, headers=headers, timeout=30) as client:
        print(f"  Importing framework: {COURSE['title']}")
        resp = client.post(
            "/api/admin/curriculum/imports",
            json={
                "adapter_key": "alberta_math_7_seed",
                "framework_id": "alberta-math-7",
                "title": "Alberta Mathematics Grade 7",
                "jurisdiction": "Alberta",
                "subject": "mathematics",
                "grade_band": "7",
                "framework_version": "2022",
                "source_label": "Alberta Mathematics Grade 7 seed",
                "source_uri": "https://curriculum.learnalberta.ca/curriculum/en/pos/MAT_79/MATH7",
                "tags": ["alberta", "grade-7", "mathematics"],
            },
        )
        resp.raise_for_status()
        imported = resp.json()
        verification = imported["verification_report"]
        print(
            "  Imported artifacts:"
            f" {verification['course_count']} course,"
            f" {verification['strand_count']} strands,"
            f" {verification['outcome_count']} outcomes,"
            f" {verification['knowledge_component_count']} knowledge components"
        )

        if verification["issue_count"]:
            print(
                "  Verification:"
                f" {verification['error_count']} errors,"
                f" {verification['warning_count']} warnings"
            )

        resp = client.post(
            f"/api/admin/curriculum/imports/{imported['import_id']}/publish",
            json={"force": False},
        )
        resp.raise_for_status()
        snapshot = resp.json()

        print(
            "\nPublished Alberta Math 7 snapshot:"
            f" {snapshot['snapshot_id']} with"
            f" {len(snapshot['runtime_strand_ids'])} strands,"
            f" {len(snapshot['runtime_outcome_ids'])} outcomes,"
            f" {len(snapshot['runtime_knowledge_component_ids'])} knowledge components"
        )


def main() -> None:
    import httpx

    parser = argparse.ArgumentParser(
        description="Seed Alberta Math 7 curriculum into Dibble"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Dibble API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for authentication (optional)",
    )
    args = parser.parse_args()

    print(f"Seeding Alberta Math 7 curriculum → {args.base_url}")
    try:
        seed(args.base_url, args.api_key)
    except httpx.HTTPStatusError as exc:
        print(
            f"\nERROR: {exc.response.status_code} {exc.response.text}", file=sys.stderr
        )
        sys.exit(1)
    except httpx.ConnectError:
        print(f"\nERROR: Could not connect to {args.base_url}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
