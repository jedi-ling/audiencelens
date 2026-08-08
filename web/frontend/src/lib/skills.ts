import { SKILLS } from './mock-data'
import { fetchSkills } from './api'
import { getToken } from './apiClient'

/**
 * 不参与评审流程的技能。
 *
 * persona_generate 在后端 PersonaService._SKILL_PROMPT_HINTS 里没有任何提示语，
 * 带着它创建评审跑出来的就是一次普通评审，skill_type 只被落库当标签；真正能生成
 * 人格的是 POST /api/generate-personas，那是另一条链路（lib/api.ts 的
 * generatePersonas 封装已对齐后端 PersonaGenerateRequest，但当前仍无调用点）。
 *
 * 处理方式选的是「摘掉入口」而不是「接上生成端点」：接生成端点要加一个展示
 * 生成结果的页面、决定生成出来的人格存到哪里——那是一个新功能，
 * 不是修一个洞。而留着这个按钮的代价是确定的：用户花掉一次评审额度，拿回一份和
 * 他选的技能毫无关系的报告，且全程没有任何提示。所以先让它不可点，并说明原因。
 *
 * 这份名单是前端对后端行为的镜像，后端加/减提示语时不会自动同步——真正的解法是
 * 后端在 /api/skills 里透出一个「这个技能会不会改变评审行为」的字段。卡口测试见
 * web/backend/tests/test_skill_entry_honesty.py，后端改了这边不改就会红。
 */
export const NON_REVIEW_SKILL_TYPES = ['persona_generate']

/** 技能详情端点（GET /api/skills/{skill_type}）的真实响应形状。
 *
 *  为什么不用 lib/api.ts 的 fetchSkill：它声明的返回类型 SkillDetail
 *  （name/description_zh/task_types/persona_count/use_cases）与真实响应
 *  （skill_type/name/description/task_types/...）没有一个字段能对上，persona_count
 *  后端从来就没有过。照着那个类型读只会读到一片 undefined。这里按后端 schemas 的
 *  SkillTypeResponse 逐字声明；等 api.ts 的类型修好，这段应当并回去。 */
export type SkillTruth = {
  type: string
  name: string
  description: string
  /** 后端声明的任务类型。null 表示**后端没说**（不是「一个都不支持」），
   *  这种情况下不能拿它去裁用户的选项——后端创建评审时对组合本就零校验。 */
  taskTypes: string[] | null
  /** 本地才有的展示装饰（图标/配色/用例），后端新增技能而前端还没配时是 undefined */
  deco?: (typeof SKILLS)[number]
}

type SkillDetailResponse = {
  skill_type: string
  name: string
  description: string
  task_types?: string[] | null
}

/**
 * 以 /api/skills 为准列出技能，再逐个取详情补上真实的 task_types。
 *
 * 详情用 allSettled 而不是 all：某个技能的详情取不到时，那张卡照样要能显示
 * （名字和描述已经从列表拿到了），只是它的任务类型标记为「后端没说」。用 all 的话
 * 一个 404 会让整页退化成加载失败，比现状还糟。
 */
export async function loadSkillTruth(): Promise<SkillTruth[]> {
  const list = await fetchSkills()
  const details = await Promise.allSettled(
    list.map(async (s): Promise<SkillDetailResponse> => {
      const token = getToken()
      const res = await fetch(`/api/skills/${encodeURIComponent(s.skill_type)}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    })
  )
  return list.map((s, i) => {
    const d = details[i]
    const taskTypes = d.status === 'fulfilled' ? d.value.task_types ?? null : null
    return {
      type: s.skill_type,
      name: s.name,
      description: s.description,
      taskTypes,
      deco: SKILLS.find((x) => x.type === s.skill_type),
    }
  })
}
