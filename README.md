Warning: fsx was declared with const; use let for reassignable variables.
# 合成生物学与 iGEM Skill 套装

版本 1.1.0 · 发布文件制作日期 2026-09-15

面向学生、导师及教研团队的六个独立Skill。每个文件夹都含SKILL.md、界面元数据、介绍、操作指南和教学指南，并配有实际需要的模板、示例或脚本。

| Skill | 作用 | 运行要求 |
|---|---|---|
| [synbio-expert](skills/synbio-expert/docs/介绍.md) | 以证据卡完成科学答疑、论文研读和中国研究者资料说明 | 支持Skill的AI；当前事实需联网或可读资料 |
| [synbio-planner](skills/synbio-planner/docs/介绍.md) | 用成果图、依赖图和证据闸门规划项目、课程与活动 | 支持Skill的AI |
| [igem-mentor](skills/igem-mentor/docs/介绍.md) | 按年份和角色提供双语赛事证据与行动建议 | 支持Skill的AI及可读取的官方资料 |
| [synbio-knowledge-base](skills/synbio-knowledge-base/docs/介绍.md) | 按项目维护本地证据账本和可复核的关键词命中 | Python 3.10+，标准库 |
| [synbio-video](skills/synbio-video/docs/介绍.md) | 将科学主张映射到镜头、视觉类型与制作状态 | 规划无需脚本；合成需要Python 3.9+和FFmpeg |
| [synbio-cue-cards](skills/synbio-cue-cards/docs/介绍.md) | 生成带触发点、证据与交接动作的多人提示卡 | HTML使用Python 3.10+；PDF另需ReportLab和中文字体 |

建议从三个核心Skill开始，再按交付需求使用辅助模块。它们可以独立安装，不需要把所有Skill一次加载进对话。

## 快速使用

1. 按 [安装说明](INSTALL.md) 安装所需Skill，保持其完整目录。
2. 在所用Agent中调用Skill，例如“使用 $synbio-planner，为零实验基础学生设计四次合成生物学课程”。不同平台的选择器语法见安装说明。
3. 提供任务背景和可用资料。涉及当前iGEM政策时，要求对应年份的官方来源。
4. 若需运行工具，从对应Skill的操作指南查看依赖和命令；工具不会因安装Skill而自动运行。

## 本版内容与范围

- 中国专家初始资料覆盖陈国强、戴俊彪、覃重军，附官方链接与核验范围；可以继续扩充，不表示人物排名或授权。
- iGEM提供六类工作流及资料导航种子。部分官方页面只有搜索摘录可读或依赖JavaScript，核验状态已明确标注；未打包未经确认的费用或deadline。
- 本地知识库提供关键词检索与项目筛选；它不等同于云端语义搜索或公开服务的用户认证。
- 视频生成服务及MemOS云端未内置，使用用户自己的已授权平台时再接入。视频脚本合成已有素材，不自动创造实验画面。
- 手卡支持结构化文本的HTML/PDF，不承诺原始Word、公式或科研图表的无损转换。
- iGEM Mentor是可接入Chatbot的指导层，本包不包含网站、账号后台或自动年度同步服务。

科学内容、赛事规则、实际实验/访谈和成果归属应有真实证据。所有示例为教学或工具示例；不能将示例当作本队伍完成的研究。

测试范围见 [验证报告](VALIDATION.md)，独立重构和相似度检查见 [原创性审查](ORIGINALITY-REVIEW.md)，参考范围见 [来源说明](PROVENANCE.md)。新编写文件按 [MIT许可](LICENSE.txt) 分发；外部论文、页面、商标、字体和工具仍受各自权利约束。
