<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuth } from '@/shared/state/auth'
import { IC } from '@/shared/lib/icons'
import ScoreBar from '@/shared/ui/ScoreBar.vue'

const router = useRouter()
const auth = useAuth()
const start = () => router.push(auth.loggedIn ? '/new' : '/signup')
const toFeat = () => document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })

const feats: [string, string][] = [
  ['멀티모달 발표 평가', '영상 한 번으로 발화 속도, 유창성, 제스처, 시선을 시간축에서 함께 봐요.'],
  ['구간별 리포트', '잘한 점과 고칠 점을 구간마다 정리하고, 해당 구간만 바로 다시 볼 수 있어요.'],
  ['회차별 추이', '회차마다 점수가 어떻게 달라졌는지 항목별로 이어서 보여드려요.'],
  ['발표 시간 점검', '목표 시간과 비교하고, 실제 발표 시간과의 차이를 짚어줘요.'],
  ['전사문 확인', '내가 한 말을 시간순으로 글로 확인하고, 눌러서 그 장면으로 이동해요.'],
  ['턴바이턴 질의응답 (준비 중)', '분석한 영상을 바탕으로 심사위원처럼 질문하는 질의응답은 곧 제공돼요.'],
]
const steps: [string, string, string, 'a' | 'b' | 'c'][] = [
  ['01', '프로젝트를 만들어요', '발표 제목과 주제, 최종 발표일, 목표 시간(최대 30분)을 정해요.', 'a'],
  ['02', '영상을 올려요', '리허설 영상을 올리면 AI가 음성과 영상을 비동기로 분석해요.', 'b'],
  ['03', '리포트로 고쳐요', '종합 점수, 항목별 점수, 구간별 피드백을 보고 다음 회차에 반영해요.', 'c'],
]
const ILL = [
  '<circle cx="62" cy="62" r="34" fill="#fff" opacity=".85"/><circle cx="98" cy="62" r="34" fill="var(--pri)" opacity=".75"/><circle cx="80" cy="88" r="30" fill="var(--sky)" opacity=".7"/>',
  '<g fill="var(--pri)">' + [18, 34, 52, 40, 66, 30, 48, 22].map((h, i) => `<rect x="${26 + i * 16}" y="${100 - h}" width="9" height="${h}" rx="4.5" opacity="${0.45 + i * 0.07}"/>`).join('') + '</g>',
  '<polyline points="22,110 56,82 86,94 138,40" fill="none" stroke="var(--pri)" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="138" cy="40" r="10" fill="#fff" stroke="var(--pri)" stroke-width="5"/>',
  '<circle cx="80" cy="80" r="42" fill="none" stroke="#fff" stroke-width="14" opacity=".85"/><path d="M80 38a42 42 0 1 1-37 62" fill="none" stroke="var(--pri)" stroke-width="14" stroke-linecap="round"/>',
  '<rect x="30" y="38" width="100" height="22" rx="11" fill="#fff" opacity=".9"/><rect x="30" y="68" width="76" height="22" rx="11" fill="var(--pri)" opacity=".8"/><rect x="30" y="98" width="52" height="22" rx="11" fill="var(--sky)" opacity=".85"/>',
  '<circle cx="80" cy="80" r="44" fill="#fff" opacity=".9"/><path d="M58 82l16 16 30-34" fill="none" stroke="var(--pri)" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>',
]
</script>

<template>
  <section class="hero">
    <span class="streak" style="width: 420px; right: -60px; top: 120px; transform: rotate(-14deg)" />
    <span class="streak" style="width: 300px; right: 80px; top: 210px; transform: rotate(-14deg)" />
    <span class="streak" style="width: 520px; right: -120px; top: 300px; transform: rotate(-14deg)" />
    <div class="hero-in">
      <span class="pill" style="padding: 6px 16px; font-size: 14px; background: #fff">AI 기반 발표 역량 분석 및 코칭 서비스</span>
      <h1>내 발표를<br /><em>데이터</em>로 연습하고,<br />다음 회차에 반영하세요</h1>
      <p class="lead" style="max-width: 600px; margin: 26px 0 0; font-size: 18px; line-height: 1.75">
        발표 영상을 올리면 AI가 말의 속도, 유창성, 제스처, 시선을 시간축에서 분석한 리포트를 드려요. 같은 발표를 반복하며 점수가 어떻게 달라지는지 확인해 보세요.
      </p>
      <div style="margin-top: 34px; display: flex; gap: 12px; flex-wrap: wrap">
        <button class="btn btn-p btn-l" @click="start">시작하기</button>
        <button class="btn btn-l" style="background: transparent; border-color: var(--ink)" @click="toFeat">기능 둘러보기</button>
      </div>
      <div style="margin-top: 40px; display: flex; gap: 12px 36px; flex-wrap: wrap">
        <span class="fpill"><b>최대 30분</b>발표 평가</span>
        <span class="fpill"><b>4가지</b>메인 지표 분석</span>
        <span class="fpill"><b>회차별</b>점수 추이</span>
      </div>
    </div>
  </section>

  <div class="sheet">
    <div style="max-width: 940px; margin: -8px auto 0; padding: 56px 32px 0">
      <div class="card" style="padding: 22px; box-shadow: 0 20px 50px rgba(10, 31, 92, 0.12); border: 1px solid var(--line2)">
        <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px">
          <b style="color: var(--pri-d)">분석 리포트 · 최종발표 리허설</b><span class="pill pill-g">예시 화면</span>
        </div>
        <div class="row" style="margin-top: 16px; gap: 20px">
          <div style="flex: 1 1 400px; min-width: 0">
            <div style="height: 170px; border-radius: 16px; background: linear-gradient(160deg, #1e293b, #0f172a); display: flex; align-items: center; justify-content: center" v-html="IC.play" />
            <div class="track">
              <span class="l">발화 속도</span>
              <svg viewBox="0 0 800 36" preserveAspectRatio="none" role="img" aria-label="발화 속도 예시 그래프">
                <rect x="205" width="75" height="36" fill="#FDE68A" opacity=".8" />
                <polyline vector-effect="non-scaling-stroke" fill="none" stroke="var(--pri)" stroke-width="2" points="0,22 50,18 100,24 150,16 200,26 250,34 300,30 350,20 400,22 450,16 500,24 550,20 600,18 650,24 700,20 750,22 800,18" />
              </svg>
            </div>
            <div class="track">
              <span class="l">시선</span>
              <div class="strip">
                <span style="flex: 26; background: var(--sky)" /><span style="flex: 6; background: #cbd5e1" /><span style="flex: 30; background: var(--sky)" /><span style="flex: 10; background: #cbd5e1" /><span style="flex: 28; background: var(--sky)" />
              </div>
            </div>
          </div>
          <div style="flex: 1 1 280px; display: flex; flex-direction: column; gap: 12px">
            <div style="display: flex; align-items: baseline; gap: 8px">
              <b style="font-size: 48px; line-height: 1; color: var(--pri-d)">74</b><span style="color: var(--mute)">종합 점수</span>
            </div>
            <ScoreBar label="발화 속도" :value="66" /><ScoreBar label="유창성" :value="84" /><ScoreBar label="제스처" :value="85" /><ScoreBar label="시선" :value="62" />
            <div class="warn" style="padding: 10px 14px"><b>종합 피드백</b> · 전체적으로 안정적인 발표였지만, 중반의 빠른 말 속도와 정면에서 길게 벗어난 시선이 아쉬웠어요.</div>
          </div>
        </div>
      </div>
    </div>

    <div id="how" class="num3">
      <div v-for="s in steps" :key="s[0]">
        <div v-if="s[3] === 'a'" class="shp a" />
        <div v-else-if="s[3] === 'b'" class="shp b">
          <svg viewBox="0 0 140 140"><circle cx="70" cy="70" r="46" fill="none" stroke="var(--pri)" stroke-width="2" opacity=".5" /><circle cx="70" cy="70" r="24" fill="var(--pri)" opacity=".85" /></svg>
        </div>
        <div v-else class="shp c"><i /><i /><i /></div>
        <div class="k">{{ s[0] }}</div>
        <h3>{{ s[1] }}</h3>
        <p>{{ s[2] }}</p>
      </div>
    </div>

    <section id="features" class="sec" style="padding-top: 96px">
      <h2 style="font-weight: 400; font-size: 40px; letter-spacing: -0.03em">발표 연습의 전 과정을 <b style="color: var(--pri); font-weight: 700">한 곳에서</b></h2>
      <p class="lead2">평가하고, 확인하고, 고치는 흐름을 하나로 이었어요.</p>
      <div class="fgrid">
        <div v-for="(f, i) in feats" :key="f[0]" class="ecard">
          <div class="ill"><svg viewBox="0 0 160 140" width="160" height="140" aria-hidden="true" v-html="ILL[i]" /></div>
          <div class="tx"><h3>{{ f[0] }}</h3><p>{{ f[1] }}</p></div>
        </div>
      </div>
    </section>

    <section id="privacy" class="sec">
      <div class="card" style="padding: 32px">
        <h2 style="text-align: left; font-size: 26px">영상은 동의한 만큼만</h2>
        <ul style="margin-top: 14px; font-size: 16px; line-height: 2; color: #334155; list-style: disc; padding-left: 22px">
          <li>분석 동의 후에만 영상을 분석해요.</li>
          <li>원하면 언제든 영상과 리포트를 삭제할 수 있어요. 삭제하면 바로 접근이 차단돼요.</li>
          <li>영상과 전사문은 로그에 남기지 않아요.</li>
        </ul>
      </div>
    </section>

    <section class="cta2">
      <h2>첫 리허설을 올리고,<br /><em>데이터</em>로 확인해 보세요</h2>
      <div style="margin-top: 28px; display: flex; gap: 12px; justify-content: center; flex-wrap: wrap">
        <button class="btn btn-p btn-l" @click="start">시작하기</button>
      </div>
    </section>
  </div>
</template>
