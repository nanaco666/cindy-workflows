# Cindy 数据人外观仓库

当前外观规则版本：人物 `v5-right-ear-only`（2026-10-26 修正佩戴侧），宠物 `v3-black-red-eyes`（2026-09-03）。人物现有图片仍为旧版资产，尚未按右耳规则重绘。

这个目录是 Cindy 角色与黑猫宠物的视觉锚点。后续生成内容时，优先引用 `assets/reference/` 的原始参考图，再拼接 `prompts/appearance-lock.md` 中的固定描述。不包含运行态配置。

**耳饰佩戴侧以文字规则为准：只戴在角色自身的右耳，左耳不戴，不按画面左右判断。** 现有人物三视图、细节图、耳饰拆解图及原始参考中的佩戴侧或 `LEFT EAR ONLY` 标签可能沿用旧设定；这些图片仅用于脸型、服装和饰品结构参考，不能作为佩戴侧依据。保留原文件名以记录资产版本，未将旧图重新命名为右耳版本。

## 正式资产

### 人物

- [细节图 v3](assets/character/cindy-character-details-v3-final.png)
- [三视图 v4：旧版，佩戴侧已被右耳规则取代](assets/character/cindy-character-turnaround-v4-left-ear-only.png)
- [人物耳饰独立拆解图](assets/character/cindy-earring-accessory-sheet-v1.png)

### 宠物

- [三视图 v3：黑红渐变眼](assets/pet/cindy-pet-turnaround-v3-black-red-eyes.png)
- [细节图 v3：黑红渐变眼](assets/pet/cindy-pet-details-v3-black-red-eyes.png)
- [猫项圈与银牌独立拆解图](assets/pet/cindy-collar-tag-accessory-sheet-v1.png)

### 原始参考

- [角色近景](assets/reference/cindy-original-reference.webp)
- [全身服装与鞋型](assets/reference/cindy-fullbody-costume-reference.webp)
- [海报服装与鞋型](assets/reference/cindy-update-poster-costume-reference.webp)
- [耳饰近景](assets/reference/cindy-ear-accessory-reference.webp)
- [猫眼近景](assets/reference/cindy-cat-eye-reference.png)

## 固定规则

1. 人物服装是一件浅蓝灰色收腰连衣裙，裙摆为多层荷叶边；不是吊带上衣加直筒长裙。
2. 外搭米白色宽松长款针织开衫，保留纽扣、罗纹和宽袖。
3. 鞋子是黑色亮面厚底低帮皮鞋（厚底乐福 / Mary Jane 轮廓），不是短靴、战斗靴或任何带靴筒的鞋。
4. Cindy 只有解剖学右耳（角色自身的右耳）佩戴耳饰，左耳完全不戴；总长度约 3 cm。结构是银质小圆形耳钉 + 银色细链条 + 一个侧向“>”形吊坠；这是代码极客符号。饰品结构参考独立耳饰拆解图；佩戴侧以本条右耳规则为准，忽略旧图中的左耳标注。
5. 头发为黑色至深海军蓝蓬松层次短发，带电蓝和少量猩红高光；眼睛为琥珀金棕色。
6. 黑猫为短毛黑猫，毛发贴顺，仅保留轻微脸颊/胸口柔软度；虹膜为上黑下红的垂直渐变，黑色竖瞳；禁止橙/琥珀/金/黄/棕/蓝眼睛；红色项圈，圆形银牌，银牌上有一道“一”字横向刻痕。
7. 猫的项圈与银牌单独参考 [猫项圈与银牌独立拆解图](assets/pet/cindy-collar-tag-accessory-sheet-v1.png)。

后续生成不要引用外部旧草稿或未审核图片；以本目录正式资产为准。
