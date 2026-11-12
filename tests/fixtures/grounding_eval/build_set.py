"""Build tests/fixtures/grounding_eval/items.jsonl (deterministic; no model calls).

    python tests/fixtures/grounding_eval/build_set.py            # rewrite items.jsonl
    python tests/fixtures/grounding_eval/build_set.py --check    # exit 1 if items.jsonl is stale

Constructed items are written by hand below and their labels follow from how they are built;
the builder asserts the construction (a "verbatim" span really is in the material, an altered
number really is not, ...). It does NOT run any grounding rule to decide a label.
Real items come from real_items.jsonl (hand-labelled by reading each against its material).
See README.md in this folder.
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(HERE, "items.jsonl")

MATERIALS = {
    "zh_steam": "test-materials/03_steam商店页_深渊回响.md",
    "zh_pricing": "test-materials/04_定价页_云笔记订阅.md",
    "zh_devlog": "test-materials/05_开发日志_第7期.md",
    "en_store": "tests/fixtures/grounding_eval/materials/en_store_page_lantern_tide.md",
    "en_pricing": "tests/fixtures/grounding_eval/materials/en_pricing_page_quillbox.md",
    "en_devlog": "tests/fixtures/grounding_eval/materials/en_devlog_mossgate.md",
}

CATEGORIES = {
    1: ("verbatim", "grounded"),
    2: ("verbatim_punctuation_variant", "grounded"),
    3: ("framing_plus_verbatim", "grounded"),
    4: ("half_true", "not_grounded"),
    5: ("paraphrase_judgement", "not_grounded"),
    6: ("absence_claim", "not_grounded"),
    7: ("fabricated", "not_grounded"),
    8: ("number_changed", "not_grounded"),
}

S, P, D = "zh_steam", "zh_pricing", "zh_devlog"
ES, EP, ED = "en_store", "en_pricing", "en_devlog"

# 1 — verbatim spans: (material, span). Asserted: span is in the raw material.
VERBATIM = [
    (S, "《深渊回响》是一款黑白水墨风格的银河城探索游戏。"),
    (S, '独创的"回响"死亡机制：死亡不是失败，而是叙事的一部分'),
    (S, "非线性地图，8 种可习得能力驱动的箱庭解谜"),
    (S, "平台：Steam（Windows），暂无 Switch 计划"),
    (P, "三种方案，随时可以升级或降级，无隐藏费用"),
    (P, "版本历史保留 1 年"),
    (P, "年付享受约 26% 折扣，可随时申请按未使用月份比例退款。"),
    (D, '收到最多的反馈就是"打击感发软"'),
    (D, "音乐方面在和一位独立作曲人洽谈合作"),
    (D, "预计下个月开一轮小范围 Discord 内测，名额 50 个，感兴趣的可以在评论区留言"),
    (ES, "Lantern Tide is a hand-painted management game set on a remote lighthouse island."),
    (ES, "No combat and no fail state: a missed ship changes the story instead of ending it"),
    (ES, "36 hand-painted ships, each with its own captain and a short story told over radio"),
    (ES, "Platforms: Steam (Windows and Steam Deck); a console version is not planned yet"),
    (EP, "All plans include a 14-day free trial. No credit card is required to start."),
    (EP, "Paid subscriptions with a 5% platform fee"),
    (EP, "Annual plans can be refunded in full within the first 30 days."),
    (ED, "In the October playtest, 14 of 19 players never opened the crafting menu after the tutorial."),
    (ED, "Tools no longer break. They get dull after about 40 uses and can be sharpened at any campfire."),
    (ED, "We have not decided whether an optional mode is worth the maintenance cost."),
]

# 2 — (material, span as it is in the material, variant, what differs).
# Asserted: span is in the raw material, variant is not.
VARIANTS = [
    (S, "你扮演一名失忆的潜水员，\n在一座沉入深海的古代都市中探索、战斗、拼凑破碎的记忆。",
     "你扮演一名失忆的潜水员，在一座沉入深海的古代都市中探索、战斗、拼凑破碎的记忆。", "line break removed"),
    (S, "预计定价：$19.99", "预计定价:$19.99", "full-width colon -> half-width"),
    (S, "预计流程 12-15 小时，支持手柄与键鼠", "预计流程12-15小时,支持手柄与键鼠", "spaces removed, half-width comma"),
    (S, '独创的"回响"死亡机制：死亡不是失败，而是叙事的一部分',
     "独创的“回响”死亡机制：死亡不是失败，而是叙事的一部分", "straight quotes -> curly"),
    (P, "¥19 / 月，或 ¥168 / 年（约 ¥14/月）", "¥19/月，或¥168/年(约¥14/月)", "spaces removed, half-width brackets"),
    (P, "不会。免费版永久免费，我们不会强制升级，也不会锁定你已有的笔记。",
     "不会。免费版永久免费,我们不会强制升级,也不会锁定你已有的笔记.", "half-width punctuation"),
    (P, "可以，取消后仍可使用至当前计费周期结束，数据不会被删除，\n30 天内重新订阅可完整恢复。",
     "可以，取消后仍可使用至当前计费周期结束，数据不会被删除，30天内重新订阅可完整恢复。", "line break and spaces removed"),
    (D, "前摇从 8 帧压缩到 3-4 帧", "前摇从８帧压缩到３-４帧", "full-width digits, spaces removed"),
    (D, '内部测试的 6 个人里，5 个人明确说"感觉完全不一样了"',
     "内部测试的 6 个人里，5 个人明确说「感觉完全不一样了」", "straight quotes -> corner brackets"),
    (D, "暂时没有配音计划，\n预算有限，会优先保证文本本地化质量。",
     "暂时没有配音计划，预算有限，会优先保证文本本地化质量。", "line break removed"),
    (ES, '"The radio conversations are the best part. I wanted more of them."',
     "“The radio conversations are the best part. I wanted more of them.”", "straight quotes -> curly"),
    (ES, "Estimated length of 10 to 12 hours, with a relaxed mode that removes all timers",
     "estimated length of 10 to 12 hours,  with a relaxed mode that removes all timers.", "case, double space, trailing period"),
    (ES, "We are a team of three working from two countries.",
     "We are a team of three  working from two countries", "double space, no final period"),
    (ES, "Planned price: $16.99", "Planned price：$16.99", "half-width colon -> full-width, space dropped"),
    (EP, "$15 per month, or $144 per year", "$15 per month,or $144 per year", "space after comma dropped"),
    (EP, "Yes, as a CSV file, on every plan including Starter.",
     "yes, as a csv file, on every plan including starter.", "lower-cased"),
    (EP, "We will email you and you will have 30 days to upgrade or remove subscribers. We never delete your list.",
     "We will email you and you will have 30 days to upgrade or remove subscribers.\nWe never delete your list.", "line break inserted"),
    (ED, "The inventory went from 48 slots to 24 slots, and items of the same type now stack up to 10.",
     "The inventory went from 48 slots to 24 slots – and items of the same type now stack up to 10.", "comma -> en dash"),
    (ED, "Six of them finished the first region, compared with three of eight in the previous build.",
     "‘Six of them finished the first region, compared with three of eight in the previous build.’", "wrapped in single curly quotes"),
    (ED, "Finish the second region, which is about 60% complete",
     "Finish the second region, which is about 60 % complete", "space before percent sign"),
]

# 3 — (material, framing template with {q}, verbatim span). Every framing is used once.
# Asserted: span is in the raw material.
FRAMED = [
    (S, "页面写着「{q}」", "手绘水墨美术风格，全程黑白配色，仅在关键剧情节点出现血红色点缀"),
    (S, "原文：“{q}”", "无对话文本的叙事设计，靠环境与回响碎片讲故事"),
    (S, "开发商的话里提到：{q}", "我们是一个 4 人小团队，此前从未做过完整发售的商业游戏。"),
    (S, "发售信息一栏明确写了“{q}”", "支持语言：简体中文、英语、日语（界面与字幕，无配音）"),
    (P, "材料中的原话是：{q}", "适合重度笔记用户和自由职业者"),
    (P, "FAQ 的回答是「{q}」", "支付宝、微信支付、境内外主流信用卡（Visa/Mastercard）。"),
    (P, "团队版那一栏标注：{q}", "¥49 / 用户 / 月，最低 3 人起订"),
    (D, "日志里说：“{q}”", "我们录了一段修改前后的对比视频，会在下一期日志里放出来"),
    (D, "作者自己写道：{q}", "目前第三关的死亡率还是偏高（约 34%）"),
    (D, "引用原文——“{q}”", "加入了受击硬直反馈"),
    (ES, 'The page says "{q}".', "Repair and upgrade the lamp, the foghorn and the supply dock in any order"),
    (ES, 'Quote from the listing: "{q}"', "Languages: English, French and Japanese (text only, no voice acting)"),
    (ES, 'The developers write: "{q}"', "This is our second game; our first one sold about 8,000 copies."),
    (ES, "Under Key features it reads: {q}", "A full day-and-night cycle where every night lasts about 9 minutes of real time"),
    (EP, 'The pricing page states that "{q}"', "Monthly plans end at the close of the billing period."),
    (EP, 'According to the FAQ, "{q}"',
     "Card processing fees from our payment partner are separate from the platform fee and are passed through at cost."),
    (EP, "The Studio plan lists: {q}", "Five team seats, with extra seats at $9 each per month"),
    (ED, "In the devlog's own words: \"{q}\"", "Crafting also accounted for roughly a third of our open bug reports."),
    (ED, 'The post explicitly says, "{q}"', "Two players said they missed crafting and asked for it back as an optional mode."),
    (ED, 'Verbatim: "{q}"', "Open a wider playtest in January with 200 keys; sign-ups will be posted on our forum"),
]

# 4 — (material, verbatim fragment, fabricated addition). Content = fragment + addition.
# Asserted: fragment is in the raw material; the addition is hand-checked to be absent from it.
HALF_TRUE = [
    (S, "预计流程 12-15 小时，支持手柄与键鼠", "，并且通关后解锁双人合作模式"),
    (S, "平台：Steam（Windows），暂无 Switch 计划", "，但已确认首发加入主机订阅服务"),
    (S, "我们是一个 4 人小团队，此前从未做过完整发售的商业游戏。", "不过主创曾在大厂主导过三款上线项目。"),
    (S, "支持语言：简体中文、英语、日语（界面与字幕，无配音）", "，发售后三个月内补上中文配音"),
    (P, "笔记数量无限制", "，而且所有笔记默认端到端加密"),
    (P, "邮件支持，24 小时内响应", "，节假日提供电话专线"),
    (P, "年付享受约 26% 折扣，可随时申请按未使用月份比例退款。", "学生凭证件还能再减半。"),
    (P, "99.9% SLA 保证", "，未达标按月费十倍赔付"),
    (D, "音效提前 1 帧播放", "，同时把背景音乐整体降了半个调"),
    (D, "预计下个月开一轮小范围 Discord 内测，名额 50 个", "，入选者可以获得正式版免费兑换码"),
    (ES, "Estimated length of 10 to 12 hours, with a relaxed mode that removes all timers",
     " and a New Game Plus that doubles the fleet"),
    (ES, "Planned price: $16.99", ", with a permanent 40% discount for owners of the studio's first game"),
    (ES, "We have been building Lantern Tide for 20 months and we will post a public demo before release.",
     " The demo will include online co-op."),
    (ES, "Languages: English, French and Japanese (text only, no voice acting)",
     ", and full Spanish voice-over is confirmed for launch"),
    (EP, "Unlimited emails", ", including SMS campaigns"),
    (EP, "Email support with replies within one business day", " and a dedicated phone line on weekends"),
    (EP, "Yes, as a CSV file, on every plan including Starter.", " Exports are limited to once per month."),
    (EP, "Priority support and a 99.5% delivery uptime target", ", backed by service credits"),
    (ED, "Tools no longer break. They get dull after about 40 uses and can be sharpened at any campfire",
     ", which costs two iron ingots each time."),
    (ED, "Open a wider playtest in January with 200 keys; sign-ups will be posted on our forum",
     ", and every tester gets the full game for free"),
]

# 5 — paraphrase / summary with the reviewer's judgement: (material, content). Hand-written.
PARAPHRASE = [
    (S, "这游戏主打死了以后留下线索的玩法，听着新鲜，但我怀疑撑不了十几个小时。"),
    (S, "美术走的是黑白国风路线，偶尔才上一点红，辨识度应该不低。"),
    (S, "团队规模很小而且没有发售经验，我对他们能否按时交付持保留态度。"),
    (S, "内测反馈里有人抱怨找不到路，说明地图引导做得不够。"),
    (P, "中档套餐按年买比按月买划算不少，对长期用户是个实在的优惠。"),
    (P, "不花钱的那一档限制很多，设备数量卡得尤其死，基本只能当试用。"),
    (P, "企业档要先找销售谈，价格不够透明，小团队会嫌麻烦。"),
    (D, "他们把出招前的准备动作缩短了一大半，这对手感的改善应该是实打实的。"),
    (D, "内部试玩的人大多认可这次改动，不过样本太少，说服力有限。"),
    (D, "制作组在向玩家征集描述手感的词汇，态度挺诚恳，但也暴露出他们自己没有明确标准。"),
    (ES, "The game is basically a cozy lighthouse sim, and I doubt the loop stays fresh past the midpoint."),
    (ES, "Nothing can really go wrong for the player, which sounds relaxing but removes any tension."),
    (ES, "A tiny studio with one modest release behind it is promising a lot here; I'd wait for the demo."),
    (ES, "Testers liked the chatter over the radio but found the opening sluggish, so pacing is the obvious risk."),
    (EP, "The middle tier is cheaper if you pay yearly, which is a fair deal for anyone who plans to stick around."),
    (EP, "The free tier is tight on audience size and puts their logo on your mail, so it's really just a taster."),
    (EP, "The team tier forces yearly billing, which is a commitment many small groups will hesitate over."),
    (ED, "Most testers ignored the item-making feature, so removing it was the sensible call."),
    (ED, "Halving the backpack while letting things pile up feels like a wash; I'm not convinced it improves anything."),
    (ED, "The follow-up numbers look better, but with so few people involved I wouldn't read much into them."),
]

# 6 — absence claims: (material, content). Hand-written. A statement about what is missing
# cannot be a quote, so it does not belong under `direct` whether or not it is true.
ABSENCE = [
    (S, "页面完全没有提到是否支持 Steam Deck。"),
    (S, "材料里没有任何关于退款政策的说明。"),
    (S, "整页没有出现游戏的实机截图或预告片链接。"),
    (S, "商店页从头到尾没提多人模式。"),
    (P, "定价页没有写自动续费前会不会提醒用户。"),
    (P, "页面没有说明教育优惠或学生折扣。"),
    (P, "没有看到任何关于数据存储地点或加密方式的描述。"),
    (D, "日志没有给出新版本的具体上线日期。"),
    (D, "文中没有提到这次重做花了多少预算。"),
    (D, "全文没有任何地方说明游戏会登陆哪些平台。"),
    (ES, "The page never mentions controller support."),
    (ES, "There is no information about a refund policy anywhere in the listing."),
    (ES, "The store page does not say whether there will be a soundtrack."),
    (ES, "Nothing in the material explains how saves work."),
    (EP, "The pricing page does not mention any discount for nonprofits."),
    (EP, "There is no statement about where subscriber data is stored."),
    (EP, "The page never says whether prices include tax."),
    (ED, "The devlog gives no release date for the full game."),
    (ED, "The post does not mention how many people work on the project."),
    (ED, "Nowhere does the update say which platforms the game will ship on."),
]

# 7 — fully fabricated: (material, content). Hand-written, hand-checked to be absent.
FABRICATED = [
    (S, "游戏首发即包含 40 名可操控角色和在线排位赛。"),
    (S, "官方承诺发售首周全球同步半价促销。"),
    (S, "本作由曾获年度独立游戏大奖的制作人亲自监制。"),
    (S, "购买豪华版可获赠原声音乐集与设定画册。"),
    (P, "企业客户可以申请私有化部署到自己的服务器。"),
    (P, "所有套餐都附赠 100GB 云端图床空间。"),
    (P, "新用户首月只需一元即可体验全部高级功能。"),
    (D, "本期更新新增了三名可选主角和一套连招编辑器。"),
    (D, "制作组宣布已经与发行商签下全球发行合约。"),
    (D, "下个版本会开放创意工坊，支持玩家自制关卡。"),
    (ES, "The game launches with a 4-player online co-op campaign."),
    (ES, "Pre-orders include an art book and the original soundtrack."),
    (ES, "The studio previously won a major award for narrative design."),
    (ES, "A Nintendo Switch port will arrive on launch day."),
    (EP, "Enterprise customers can host the service on their own servers."),
    (EP, "Every plan comes with a free custom illustration pack."),
    (EP, "Students get 50% off after verifying a school address."),
    (ED, "The update adds a fishing minigame and three new biomes."),
    (ED, "The team signed a publishing deal that covers console releases."),
    (ED, "Mod support will open to all backers next month."),
]

# 8 — one figure altered: (material, original span, altered span).
# Asserted: original is in the raw material, altered is not, and they differ.
NUMBER_CHANGED = [
    (S, "预计流程 12-15 小时，支持手柄与键鼠", "预计流程 12-25 小时，支持手柄与键鼠"),
    (S, "预计定价：$19.99", "预计定价：$29.99"),
    (S, "非线性地图，8 种可习得能力驱动的箱庭解谜", "非线性地图，6 种可习得能力驱动的箱庭解谜"),
    (S, "预计发售日期：2027 年第一季度", "预计发售日期：2028 年第一季度"),
    (P, "最多 200 篇笔记", "最多 500 篇笔记"),
    (P, "¥19 / 月，或 ¥168 / 年（约 ¥14/月）", "¥19 / 月，或 ¥198 / 年（约 ¥14/月）"),
    (P, "年付享受约 26% 折扣，可随时申请按未使用月份比例退款。", "年付享受约 36% 折扣，可随时申请按未使用月份比例退款。"),
    (D, "敌人被打中时会有 2 帧的停顿 + 屏幕轻微震动", "敌人被打中时会有 5 帧的停顿 + 屏幕轻微震动"),
    (D, "预计下个月开一轮小范围 Discord 内测，名额 50 个，感兴趣的可以在评论区留言",
     "预计下个月开一轮小范围 Discord 内测，名额 500 个，感兴趣的可以在评论区留言"),
    (D, "目前第三关的死亡率还是偏高（约 34%）", "目前第三关的死亡率还是偏高（约 54%）"),
    (ES, "36 hand-painted ships, each with its own captain and a short story told over radio",
     "63 hand-painted ships, each with its own captain and a short story told over radio"),
    (ES, "Planned price: $16.99", "Planned price: $19.99"),
    (ES, "Estimated length of 10 to 12 hours, with a relaxed mode that removes all timers",
     "Estimated length of 10 to 20 hours, with a relaxed mode that removes all timers"),
    (ES, "This is our second game; our first one sold about 8,000 copies.",
     "This is our second game; our first one sold about 80,000 copies."),
    (EP, "Up to 5,000 subscribers", "Up to 50,000 subscribers"),
    (EP, "$15 per month, or $144 per year", "$15 per month, or $120 per year"),
    (EP, "Paid subscriptions with a 3% platform fee", "Paid subscriptions with a 8% platform fee"),
    (ED, "In the October playtest, 14 of 19 players never opened the crafting menu after the tutorial.",
     "In the October playtest, 4 of 19 players never opened the crafting menu after the tutorial."),
    (ED, "The inventory went from 48 slots to 24 slots, and items of the same type now stack up to 10.",
     "The inventory went from 48 slots to 32 slots, and items of the same type now stack up to 10."),
    (ED, "Open a wider playtest in January with 200 keys; sign-ups will be posted on our forum",
     "Open a wider playtest in January with 2,000 keys; sign-ups will be posted on our forum"),
]

# ---- quote-shaped items (schema with a separate `quote` field; added 2026-11) ----
# Built by pairing the hand-written pieces above with a comment (or a fabricated claim) written
# for the same material. Only `quote` is checked
# by the rule; `content` is the persona's free-text comment.
QUOTE_CATEGORIES = {
    "q1": ("quote_verbatim_plus_comment", "grounded"),
    "q2": ("quote_variant_plus_comment", "grounded"),
    "q3": ("quote_fabricated", "not_grounded"),
    "q4": ("quote_half_true", "not_grounded"),
    "q5": ("quote_number_changed", "not_grounded"),
    "q6": ("quote_is_paraphrase", "not_grounded"),
    "q7": ("quote_missing", "not_grounded"),
    # Known limit, kept visible: the quote is real but the comment asserts something the
    # material does not say. The rule accepts it because comments are not fact-checked.
    "q8": ("quote_ok_comment_fabricated", "grounded_by_rule"),
}

REAL_KINDS = {
    # real_kind -> (category number or None, label)
    "verbatim": (1, "grounded"),
    "framing_plus_verbatim": (3, "grounded"),
    "restatement_or_judgement": (5, "not_grounded"),
    "absence_claim": (6, "not_grounded"),
    "quote_plus_commentary": (None, "mixed"),
}

_material_cache = {}


def material_text(key_or_path: str) -> str:
    path = MATERIALS.get(key_or_path, key_or_path)
    if path not in _material_cache:
        with open(os.path.join(ROOT, path), encoding="utf-8") as f:
            _material_cache[path] = f.read()
    return _material_cache[path]


def _item(cat, mat, content, **extra):
    name, label = CATEGORIES[cat]
    return {"lang": mat[:2], "source": "constructed", "category": cat, "category_name": name,
            "label": label, "material": MATERIALS[mat], "content": content, **extra}


def constructed():
    items = []
    for mat, span in VERBATIM:
        assert span in material_text(mat), span
        items.append(_item(1, mat, span))
    for mat, span, variant, diff in VARIANTS:
        text = material_text(mat)
        assert span in text and variant not in text and span != variant, variant
        items.append(_item(2, mat, variant, built_from=span, difference=diff))
    framings = set()
    for mat, framing, span in FRAMED:
        assert span in material_text(mat), span
        assert framing not in framings
        framings.add(framing)
        items.append(_item(3, mat, framing.format(q=span), built_from=span, framing=framing))
    for mat, fragment, addition in HALF_TRUE:
        text = material_text(mat)
        assert fragment in text and addition.strip(" ，,。.") not in text, fragment
        items.append(_item(4, mat, fragment + addition, built_from=fragment, fabricated_part=addition))
    for cat, rows in ((5, PARAPHRASE), (6, ABSENCE), (7, FABRICATED)):
        for mat, content in rows:
            assert content not in material_text(mat), content
            items.append(_item(cat, mat, content))
    for mat, original, altered in NUMBER_CHANGED:
        text = material_text(mat)
        assert original in text and altered not in text and original != altered, altered
        items.append(_item(8, mat, altered, built_from=original))
    return items


def quote_shaped():
    items = []

    def add(cat, mat, quote, content, **extra):
        name, label = QUOTE_CATEGORIES[cat]
        item = {"lang": mat[:2], "source": "constructed", "shape": "quote", "category": cat,
                "category_name": name, "label": label, "material": MATERIALS[mat], "content": content}
        if quote is not None:
            item["quote"] = quote
        items.append({**item, **extra})

    comments, fabrications, seen = {}, {}, {}
    for mat, text in PARAPHRASE:
        comments.setdefault(mat, []).append(text)
    for mat, text in FABRICATED:
        fabrications.setdefault(mat, []).append(text)

    def pick(pool, mat, cat):
        """Cycle through the hand-written texts of the same material, per category."""
        k = seen.get((cat, mat), 0)
        seen[(cat, mat)] = k + 1
        return pool[mat][k % len(pool[mat])]

    for mat, span in VERBATIM:
        add("q1", mat, span, pick(comments, mat, "q1"))
    for mat, span, variant, diff in VARIANTS:
        add("q2", mat, variant, pick(comments, mat, "q2"), built_from=span, difference=diff)
    for mat, text in FABRICATED:
        add("q3", mat, text, pick(comments, mat, "q3"))
    for mat, fragment, addition in HALF_TRUE:
        add("q4", mat, fragment + addition, pick(comments, mat, "q4"), fabricated_part=addition)
    for mat, original, altered in NUMBER_CHANGED:
        add("q5", mat, altered, pick(comments, mat, "q5"), built_from=original)
    for mat, text in PARAPHRASE:
        add("q6", mat, text, "这是材料里的说法。" if mat.startswith("zh") else "This is what the material says.")
    for mat, _framing, span in FRAMED:
        add("q7", mat, None, span)                                  # verbatim text, but in `content`; no quote
        add("q8", mat, span, pick(fabrications, mat, "q8"))
    return items


def real():
    items = []
    with open(os.path.join(HERE, "real_items.jsonl"), encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            cat, label = REAL_KINDS[row["real_kind"]]
            material_text(row["material"])  # must exist
            items.append({
                "lang": "zh", "source": "real", "category": cat,
                "category_name": CATEGORIES[cat][0] if cat else "real_quote_plus_commentary",
                "label": label, "material": row["material"], "content": row["content"],
                "real_kind": row["real_kind"], "origin": row["origin"],
                "accepted_by_rule_at_generation": row["accepted_by_rule_at_generation"],
            })
    return items


def assign_ids_and_splits(items):
    """60/40 dev/test inside every (source, category, language) stratum, ordered by a hash of the
    content, so the split does not depend on list order and never changes for an existing item."""
    strata = {}
    for it in items:
        strata.setdefault((it["source"], it["category_name"], it["lang"]), []).append(it)
    out = []
    for key in sorted(strata):
        group = sorted(strata[key], key=lambda it: hashlib.sha256(
            (it["content"] + ("\x00" + it.get("quote", "") if it.get("shape") == "quote" else "")).encode("utf-8")
        ).hexdigest())
        n_dev = int(len(group) * 0.6 + 0.5)
        for i, it in enumerate(group):
            digest = hashlib.sha256(it["content"].encode("utf-8")).hexdigest()[:8]
            if it.get("shape") == "quote":
                digest = hashlib.sha256((it["content"] + "\x00" + it.get("quote", "")).encode("utf-8")).hexdigest()[:8]
                prefix = it["category"]
            else:
                prefix = ("r" if it["source"] == "real" else "c") + (str(it["category"]) if it["category"] else "m")
            out.append({"id": f"{prefix}-{it['lang']}-{digest}", "split": "dev" if i < n_dev else "test", **it})
    assert len({it["id"] for it in out}) == len(out)
    return out


def render() -> str:
    # shape: "content" = the pre-quote-field shape (the whole entry is in `content`);
    #        "quote"   = quote and comment in separate fields.
    old_shape = [{**it, "shape": "content"} for it in constructed() + real()]
    items = assign_ids_and_splits(old_shape + quote_shaped())
    return "".join(json.dumps(it, ensure_ascii=False) + "\n" for it in items)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    body = render()
    if args.check:
        with open(OUT, encoding="utf-8") as f:
            if f.read() != body:
                print("items.jsonl is out of date; run build_set.py")
                return 1
        return 0
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"wrote {body.count(chr(10))} items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
