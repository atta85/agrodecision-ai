"""Pydantic schemas: every agent must return data in these shapes."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


# --------------------------------------------------------------------------- input
class CaseInput(_Base):
    language: str = "en"
    country: str = "Pakistan"
    country_code: str = "PK"
    province: str = ""
    city: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    crop: str = ""
    growth_stage: str = ""
    area: Optional[float] = None
    area_unit: str = "acre"
    symptoms: list[str] = Field(default_factory=list)
    affected_range: str = "unknown"
    onset: str = "unknown"
    spread: str = "unknown"
    irrigation: str = "unknown"
    soil_texture_user: str = "unknown"
    description: str = ""          # original text in the user's language
    description_en: str = ""       # English version (after translation)
    currency: str = "PKR"
    crop_value_at_risk: Optional[float] = None
    # Optional measurements (sensors are NOT required)
    ec_ds_m: Optional[float] = None
    ph: Optional[float] = None
    temp_c: Optional[float] = None
    extra_info: str = ""           # added later through the MORE INFORMATION button


# --------------------------------------------------------------------------- agents
class Finding(_Base):
    text: str
    source_ids: list[str] = Field(default_factory=list)


class MonitoringOut(_Base):
    findings: list[Finding] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    severity: str = "unknown"  # low | moderate | high | unknown


class Hypothesis(_Base):
    name: str
    likelihood: str = "moderate"  # high | moderate | low
    evidence_for: list[str] = Field(default_factory=list)
    evidence_against: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class DiagnosisOut(_Base):
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    primary_hypothesis: str = ""
    evidence_confidence: str = "low"  # low | moderate | high
    additional_evidence_needed: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)


class InterventionOption(_Base):
    key: str
    title: str
    description: str = ""
    addresses: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    quantities: dict[str, float] = Field(default_factory=dict)  # catalogue key -> amount
    delay_days: float = 0.0
    p_loss: float = 0.5  # assumed share of the value at risk that is still lost with this option
    assumptions: list[str] = Field(default_factory=list)
    main_uncertainty: str = ""
    source_ids: list[str] = Field(default_factory=list)

    @field_validator("p_loss")
    @classmethod
    def _clip(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    @field_validator("quantities", mode="before")
    @classmethod
    def _clean_q(cls, v):
        out = {}
        for k, val in (v or {}).items():
            try:
                f = float(val)
            except (TypeError, ValueError):
                continue
            if f > 0:
                out[str(k)] = f
        return out


class InterventionOut(_Base):
    options: list[InterventionOption] = Field(default_factory=list)


class RiskFlag(_Base):
    text: str
    status: str = "needs_confirmation"  # verified | needs_confirmation
    source_ids: list[str] = Field(default_factory=list)


class OptionRisk(_Base):
    option_key: str
    flags: list[RiskFlag] = Field(default_factory=list)


class RiskOut(_Base):
    per_option: list[OptionRisk] = Field(default_factory=list)
    overall_notes: list[str] = Field(default_factory=list)


class Issue(_Base):
    severity: str = "medium"  # low | medium | high
    text: str


class CriticOut(_Base):
    issues: list[Issue] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    overconfident_claims: list[str] = Field(default_factory=list)
    confidence_adjustment: str = "none"  # none | lower | higher
    note_to_reviewer: str = ""


class OptionLine(_Base):
    key: str
    title: str
    one_line: str = ""


class FarmerSummary(_Base):
    headline: str = ""
    likely_cause_plain: str = ""
    options_plain: list[OptionLine] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class NarrativeOut(_Base):
    notes: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- deterministic
class CostLine(_Base):
    key: str
    label: str
    unit: str
    quantity: float
    unit_cost: float
    category: str
    cost: float


class CostBreakdown(_Base):
    option_key: str
    lines: list[CostLine] = Field(default_factory=list)
    unknown_items: list[str] = Field(default_factory=list)
    c_materials: float = 0.0
    c_labor: float = 0.0
    c_equipment: float = 0.0
    c_operation: float = 0.0
    c_diagnostic: float = 0.0
    c_total: float = 0.0          # C_intervention
    p_loss: float = 0.0
    c_loss: float = 0.0           # value at risk
    expected_loss: float = 0.0    # P_loss x C_loss
    exposure: float = 0.0         # EC = C_intervention + P_loss x C_loss


class ShortItem(_Base):
    key: str
    needed: float
    on_hand: Optional[float] = None
    shortfall: float = 0.0
    order_qty: float = 0.0
    lead_time_days: float = 0.0
    extra_cost: float = 0.0


class SupplyCheck(_Base):
    option_key: str
    inventory_provided: bool = False
    shortages: list[ShortItem] = Field(default_factory=list)
    not_in_inventory: list[str] = Field(default_factory=list)
    est_delay_days: float = 0.0
    feasible_now: Optional[bool] = None
    notes: list[str] = Field(default_factory=list)


class Report(_Base):
    case: CaseInput
    photo_notes: list[dict] = Field(default_factory=list)
    monitoring: MonitoringOut = Field(default_factory=MonitoringOut)
    diagnosis: DiagnosisOut = Field(default_factory=DiagnosisOut)
    options: list[InterventionOption] = Field(default_factory=list)
    costs: list[CostBreakdown] = Field(default_factory=list)
    supply: list[SupplyCheck] = Field(default_factory=list)
    risk: RiskOut = Field(default_factory=RiskOut)
    critic: CriticOut = Field(default_factory=CriticOut)
    cost_notes: list[str] = Field(default_factory=list)
    supply_notes: list[str] = Field(default_factory=list)
    summary_en: FarmerSummary = Field(default_factory=FarmerSummary)
    summary_local: Optional[FarmerSummary] = None
    sources: list[dict] = Field(default_factory=list)
    citation_checks: list[dict] = Field(default_factory=list)
    data_quality: list[str] = Field(default_factory=list)
    prices_source: str = "default"
    warnings: list[str] = Field(default_factory=list)
    demo: bool = False
