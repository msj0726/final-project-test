// 증분(스트리밍) SHA-256.
// 업로드 계약은 영상 전체의 SHA-256(hex 64자)을 요구한다. crypto.subtle.digest 는 스트리밍이 안 되어
// 500MiB 파일 전체를 메모리에 올려야 하므로, 파일을 조각 단위로 읽으며 직접 계산한다.

const PRIMES: number[] = []
for (let n = 2; PRIMES.length < 64; n++) if (PRIMES.every((p) => n % p)) PRIMES.push(n)
const frac32 = (x: number) => Math.floor((x - Math.floor(x)) * 4294967296) | 0
const K = Int32Array.from(PRIMES, (p) => frac32(Math.cbrt(p)))
const H0 = Int32Array.from(PRIMES.slice(0, 8), (p) => frac32(Math.sqrt(p)))
const rotr = (x: number, n: number) => (x >>> n) | (x << (32 - n))

export class Sha256 {
  private h = Int32Array.from(H0)
  private w = new Int32Array(64)
  private buf = new Uint8Array(64)
  private bufLen = 0
  private total = 0

  private block(b: Uint8Array, o: number) {
    const w = this.w
    for (let i = 0; i < 16; i++, o += 4) w[i] = (b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]
    for (let i = 16; i < 64; i++) {
      const a = w[i - 15]
      const c = w[i - 2]
      w[i] = (w[i - 16] + (rotr(a, 7) ^ rotr(a, 18) ^ (a >>> 3)) + w[i - 7] + (rotr(c, 17) ^ rotr(c, 19) ^ (c >>> 10))) | 0
    }
    const h = this.h
    let [a, b2, c2, d, e, f, g, hh] = [h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7]]
    for (let i = 0; i < 64; i++) {
      const t1 = (hh + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i]) | 0
      const t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b2) ^ (a & c2) ^ (b2 & c2))) | 0
      hh = g; g = f; f = e; e = (d + t1) | 0; d = c2; c2 = b2; b2 = a; a = (t1 + t2) | 0
    }
    h[0] = (h[0] + a) | 0; h[1] = (h[1] + b2) | 0; h[2] = (h[2] + c2) | 0; h[3] = (h[3] + d) | 0
    h[4] = (h[4] + e) | 0; h[5] = (h[5] + f) | 0; h[6] = (h[6] + g) | 0; h[7] = (h[7] + hh) | 0
  }

  update(data: Uint8Array) {
    this.total += data.length
    let i = 0
    if (this.bufLen) {
      const n = Math.min(64 - this.bufLen, data.length)
      this.buf.set(data.subarray(0, n), this.bufLen)
      this.bufLen += n
      i = n
      if (this.bufLen === 64) {
        this.block(this.buf, 0)
        this.bufLen = 0
      }
    }
    for (; i + 64 <= data.length; i += 64) this.block(data, i)
    if (i < data.length) {
      this.buf.set(data.subarray(i), 0)
      this.bufLen = data.length - i
    }
  }

  hex(): string {
    const total = this.total
    const pad = new Uint8Array(((this.bufLen < 56 ? 56 : 120) - this.bufLen) + 8)
    pad[0] = 0x80
    const hi = Math.floor(total / 0x20000000)
    const lo = (total << 3) >>> 0
    const o = pad.length - 8
    pad[o] = hi >>> 24; pad[o + 1] = hi >>> 16; pad[o + 2] = hi >>> 8; pad[o + 3] = hi
    pad[o + 4] = lo >>> 24; pad[o + 5] = lo >>> 16; pad[o + 6] = lo >>> 8; pad[o + 7] = lo
    this.update(pad)
    return [...this.h].map((x) => (x >>> 0).toString(16).padStart(8, '0')).join('')
  }
}

/** 파일을 4MiB 조각으로 읽으며 SHA-256(hex)을 계산. 메모리에는 한 조각만 올린다. */
export async function sha256File(file: Blob, onProgress?: (ratio: number) => void): Promise<string> {
  const CHUNK = 4 * 1024 * 1024
  const s = new Sha256()
  for (let off = 0; off < file.size; off += CHUNK) {
    s.update(new Uint8Array(await file.slice(off, off + CHUNK).arrayBuffer()))
    onProgress?.(Math.min(1, (off + CHUNK) / file.size))
  }
  return s.hex()
}
