// 평가 항목(AI API v1.4): SPEECH_RATE · FLUENCY · GESTURE · GAZE 각 0~100 정수, 가중치 0.25.
// 명세 응답에 항목 이름이 없어 화면 이름은 프론트에서 매핑한다.
export const ITEM_KEYS = ['SPEECH_RATE', 'FLUENCY', 'GESTURE', 'GAZE'] as const
export const ITEMS: [string, string][] = [
  ['SPEECH_RATE', '발화 속도'],
  ['FLUENCY', '유창성'],
  ['GESTURE', '제스처'],
  ['GAZE', '시선'],
]
export const itemLabel = (key: string) => ITEMS.find((i) => i[0] === key)?.[1] ?? key

export const HOW_MEASURED: Record<string, string> = {
  SPEECH_RATE: '음성을 글로 옮긴 뒤 10초 단위로 말하는 속도를 쟀어요. 오래 이어진 빠른 구간이 있으면 보완 필요로 봐요.',
  FLUENCY: '말버릇(음·어·그·저), 문장 중간의 긴 쉼, 음성 인식이 잘 알아듣지 못한 구간을 함께 봤어요. 발음이 좋고 나쁜지는 판정하지 않고, 다시 들어볼 구간만 표시해요.',
  GESTURE: '카메라에 손이 보인 시간만 대상으로 쟀어요. 손동작이 내용과 맞는지는 판단하지 않아요.',
  GAZE: '얼굴이 향한 방향(고개)으로 쟀어요. 눈동자나 원고를 봤는지는 알 수 없어요.',
}
