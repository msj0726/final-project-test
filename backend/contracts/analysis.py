"""AI v1.4 계약. 명세에 없는 중첩 결과 형식은 CONTRACT_DECISIONS.md의 로컬 초안이다."""

from datetime import timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from contracts.models import Contract, JobStatus, NonNegativeInt, Score

PositiveInt = Annotated[int, Field(strict=True, ge=1)]
Seconds = Annotated[float, Field(strict=True, ge=0)]
Progress = Annotated[int, Field(strict=True, ge=0, le=100)]
Stage = Literal[
    "QUEUED",
    "PREPROCESS",
    "AUDIO",
    "VIDEO",
    "ALIGN",
    "RUBRIC_RULE",
    "RUBRIC_HEURISTIC",
    "SCORE_AGGREGATE",
    "FEEDBACK",
    "DONE",
    "FAILED",
]
STAGE_STATUS = {
    "QUEUED": "QUEUED",
    "PREPROCESS": "EXTRACTING",
    "AUDIO": "ANALYZING",
    "VIDEO": "ANALYZING",
    "ALIGN": "ANALYZING",
    "RUBRIC_RULE": "SCORING",
    "RUBRIC_HEURISTIC": "SCORING",
    "SCORE_AGGREGATE": "SCORING",
    "FEEDBACK": "SCORING",
    "DONE": "DONE",
    "FAILED": "FAILED",
}


class AnalysisRequest(Contract):
    job_id: UUID
    analysis_id: UUID
    attempt: PositiveInt
    model_version: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    target_minutes: NonNegativeInt = 0


class Utterance(Contract):
    seq: PositiveInt
    start_sec: Seconds
    end_sec: Seconds
    text: str

    @model_validator(mode="after")
    def ordered_interval(self):
        if self.start_sec >= self.end_sec:
            raise ValueError("startSec < endSec여야 합니다")
        return self


class Transcript(Contract):
    utterances: list[Utterance]

    @model_validator(mode="after")
    def contiguous_sequence(self):
        if [u.seq for u in self.utterances] != list(range(1, len(self.utterances) + 1)):
            raise ValueError("seq는 1부터 연속 증가해야 합니다")
        return self

    def validate_duration(self, duration_sec: float) -> None:
        if any(u.end_sec > duration_sec for u in self.utterances):
            raise ValueError("발화가 영상 길이를 넘었습니다")


class UtterancesWrite(Transcript):
    attempt: PositiveInt


class ResultRef(Contract):
    report_key: str = Field(min_length=1)


class Failure(Contract):
    code: str = Field(min_length=1)
    retryable: bool = Field(strict=True)


class AnalysisEvent(Contract):
    event_id: UUID
    analysis_id: UUID
    attempt: PositiveInt
    status: JobStatus
    stage: Stage
    progress: Progress
    occurred_at: AwareDatetime
    result: ResultRef = None
    failure: Failure = None

    @model_validator(mode="after")
    def consistent_state(self):
        if STAGE_STATUS[self.stage] != self.status.value:
            raise ValueError("stage/status 불일치")
        if self.occurred_at.utcoffset() != timedelta(0):
            raise ValueError("occurredAt은 UTC여야 합니다")
        if (self.status == JobStatus.DONE) != (self.result is not None):
            raise ValueError("DONE만 result를 포함해야 합니다")
        if (self.status == JobStatus.FAILED) != (self.failure is not None):
            raise ValueError("FAILED만 failure를 포함해야 합니다")
        if self.status == JobStatus.DONE and self.progress != 100:
            raise ValueError("DONE progress는 100이어야 합니다")
        return self


class Interval(Contract):
    from_sec: Seconds
    to_sec: Seconds

    @model_validator(mode="after")
    def ordered_interval(self):
        if self.from_sec >= self.to_sec:
            raise ValueError("fromSec < toSec여야 합니다")
        return self


class Evidence(Interval):
    signal: str
    value: float | None
    reason: str | None

    @model_validator(mode="after")
    def missing_reason(self):
        if self.value is None and not self.reason:
            raise ValueError("관찰 불가 값은 사유가 필요합니다")
        return self


class ItemScore(Contract):
    rubric_item_id: UUID
    item_key: str
    score: Score
    weight: Annotated[float, Field(strict=True, gt=0)]
    evidence: list[Evidence] = Field(min_length=1)


class Versions(Contract):
    model: str
    rubric: str


class Segment(Interval):
    kind: str
    feedback: str


class Coaching(Contract):
    strengths: list[str]
    improvements: list[str]
    actions: list[str]


class TimeCheck(Contract):
    actual_minutes: Seconds
    delta_minutes: float | None


class ExpectedQuestion(Contract):
    kind: str
    text: str


class Report(Contract):
    analysis_id: UUID
    project_id: UUID
    round_no: PositiveInt
    status: Literal["DONE"]
    total_score: Score
    scores: list[ItemScore] = Field(min_length=4, max_length=4)
    versions: Versions
    segments: list[Segment]
    timeline: dict[str, list[Evidence]]
    coaching: Coaching
    target_minutes: NonNegativeInt
    time_check: TimeCheck
    content_check: None
    expected_questions: list[ExpectedQuestion]
    quality: Literal["NORMAL", "DEGRADED"]
    limitations: list[str]

    @model_validator(mode="after")
    def unique_items_and_time_check(self):
        if {s.item_key for s in self.scores} != {"SPEECH_RATE", "FLUENCY", "GESTURE", "GAZE"}:
            raise ValueError("네 평가 항목이 정확히 하나씩 필요합니다")
        if any(s.weight != 0.25 for s in self.scores):
            raise ValueError("ACTIVE 루브릭의 네 항목 가중치는 각각 0.25여야 합니다")
        if len({s.rubric_item_id for s in self.scores}) != len(self.scores):
            raise ValueError("중복 rubricItemId")
        if len({s.item_key for s in self.scores}) != len(self.scores):
            raise ValueError("중복 itemKey")
        expected = (
            self.time_check.actual_minutes - self.target_minutes if self.target_minutes else None
        )
        if expected is None:
            if self.time_check.delta_minutes is not None:
                raise ValueError("목표 시간 0이면 차이는 null")
        elif (
            self.time_check.delta_minutes is None
            or abs(self.time_check.delta_minutes - expected) > 1e-9
        ):
            raise ValueError("시간 차이 불일치")
        return self

    def validate_context(
        self, job: AnalysisRequest, duration_sec: float, rubric_items: dict[UUID, tuple[str, float]]
    ) -> None:
        if (
            self.analysis_id != job.analysis_id
            or self.versions.model != job.model_version
            or self.versions.rubric != job.rubric_version
            or self.target_minutes != job.target_minutes
        ):
            raise ValueError("작업/버전/목표시간 불일치")
        if {s.rubric_item_id: (s.item_key, s.weight) for s in self.scores} != rubric_items:
            raise ValueError("루브릭 항목/가중치 불일치")
        intervals = [
            *self.segments,
            *(e for s in self.scores for e in s.evidence),
            *(e for points in self.timeline.values() for e in points),
        ]
        if any(e.to_sec > duration_sec for e in intervals):
            raise ValueError("근거/구간이 영상 길이를 넘었습니다")
        if abs(self.time_check.actual_minutes * 60 - duration_sec) > 1e-6:
            raise ValueError("실제 영상 길이 불일치")
