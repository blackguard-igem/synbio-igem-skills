# 安装与团队分发

## 压缩包结构

完整包解压后得到 synbio-igem-skills-v1.1.0，其中skills目录内有六个Skill。单独Skill包解压后直接得到与Skill同名的文件夹；其内部必须保留SKILL.md、agents、docs以及references/assets/scripts等实际存在的目录。

按需安装完整Skill文件夹，不要只复制SKILL.md或把多个Skill的内容合并到一个目录。发现同名旧版时先比较和备份，不直接覆盖团队修改。

## Codex本地使用

按2026-09-14取得的 [OpenAI官方Skill文档](https://developers.openai.com/codex/skills)：个人技能目录为用户目录下的 .agents/skills，项目技能目录为项目中的 .agents/skills。将所需的六个文件夹复制到该目录；例如安装后应能找到 .agents/skills/synbio-expert/SKILL.md。

Windows个人目录可从环境变量USERPROFILE定位，macOS/Linux使用自己的用户目录。若组织或旧版本指定了不同目录，以所用客户端配置为准。这个发布包不会自动更改本机的配置或安装位置。

Codex CLI/IDE可通过 $skill-name 或技能选择器调用；ChatGPT中使用支持的Skill选择器。平台是否支持本地脚本、网络读取和独立Skill，取决于对应产品形态与配置。更新后未出现时按官方说明重启客户端。

## 其他Agent与Chatbot

支持SKILL.md标准的宿主可读取这些文件。否则由开发者加载入口指令，并实现按需读取附属资料的能力。仅将zip上传为聊天附件不保证安装成功。独立Chatbot接入详见 [iGEM接入说明](skills/igem-mentor/docs/Chatbot接入说明.md)。

本套装是本地Skill文件分发包，没有插件市场manifest或上架申请。若以后选择插件市场渠道，需要按该平台的规范另行封装；不影响本地Skill使用。

## 脚本依赖

- 知识库：Python 3.10+，无需云端账号。
- 视频：Python 3.9+、含所需编码器的FFmpeg；具体命令与参数见对应操作指南。
- 手卡：Python 3.10+；HTML模式使用Python标准库；PDF模式按对应requirements.txt安装ReportLab并指定支持中文的字体。

安装第三方依赖使用自己的虚拟环境；不要把个人密钥、字体文件、数据库、生成视频或学生档案放进发布目录。外部软件许可证由其提供方决定，本包不附带这些二进制文件或字体。

## 验证安装

先请求一个概念解释、一个课程计划和一个需引用来源的iGEM问题，确认Skill确实被宿主选中。运行辅助工具前执行 --help，随后用随包示例验证。核验日期属于资料版本，不代表用户当前会话已经联网核验。
