# Spot Micro 四足机器人中文攻略

![Spot Micro Walking](docs/assets/spot_micro_walking.gif)

视频来源（打不开没关系，它不是很重要）: https://www.youtube.com/watch?v=S-uzWG9Z-5E


致谢/Credit to:

我们的所有代码来自于Mike的开源仓库：https://github.com/mike4192/spotMicro

Our codes are from Mike's repository

模型原型来自于 Spot Micro AI 社区：https://gitlab.com/custom_robots/spotmicroai

Our models are based from Spot Micro AI Community

这份中文攻略的主要工作是把英文开源社区的内容翻译成中文、把整理得更好读一些。

Our contribution is more about tranlating those great open-sourced technical knowledge into Chinese with a more beginner-friendly mind map.

## 仓库结构

仓库的软件、素材与本地化资料已经重新分层，详细用途见 `docs/仓库结构说明.md`。若要查找 ROS 镜像代码，请进入 `软件部分/`；若需中文教学材料或自研包，请依次查看 `软件部分/docs_cn/` 与 `软件部分/extensions/`；公共图像统一放在 `docs/assets/`。


## 简单说说关于机器人的那些事儿
机器人无非就是电脑通过软件控制硬件行动，把电脑和各种硬件连起来并不难，难点往往在基础的物理、电路知识，和指挥硬件“如何运动”的数学策略。这里且不展开描述那些难点，你现在需要知道的就是，我们马上要做的事情，完全不会涉及到它们。

我们现在要做的事情，是把设计好的硬件用电线或者无线信号连起来，然后通过电脑向它们发出一些简单的指令，让硬件“听懂”我们的指令并且乖乖动起来！也许你现在觉得电脑能让硬件动起来真神奇（我也这么想），但其实最早发明电脑的先辈们都是先用电脑控制硬件，之后花了好长时间才终于造出我们现在熟悉的高级计算机，反而我们居然不需要弄懂计算机里面的原理，就可以直接在软件层面使用了！说实话，老人们也许会觉得我们这样子才是真的不可思议。（这里其实涉及到了很本质的计算机的思想，且不展开多说了，如果有需要，可以联系我搞个小课堂什么的）

所以，你不妨长出一口气，小菜一碟~

我们的大致步骤是：购买硬件 => 尝试用你的电脑和狗狗的电脑通话 => 尝试用狗狗的电脑指挥硬件 => 把硬件组装起来 => 让狗狗动起来！

下面马上开始！

## 硬件准备
硬件包括3D打印文件和其它可以直接购买到的东西，3D打印需要你联系3D打印店家，把相应的文件发过去打印。

硬件所需的全部物料清单都在“硬件部分”文件夹里，里面有详细的介绍。这里建议你（除非本身比较懂）最好和我用完全一样的硬件，因为不同的硬件之间合作的方式会有差异，为了避免不必要的差异，和我保持一致是最安全的。


## 软件上手
软件主要由三部分组成：测试、校准、运行。

全部代码都在“软件部分”文件夹里，里面有详细的介绍。我同样建议你和我用同样的系统、软件，因为不同的软件之间合作的方式也有差异，不同的系统很可能也内置了不同的软件，导致同样的指令没办法起到相同的效果。为了避免不必要的差异，和我保持一致是最安全的。

## 拓展链接
这部分没有翻译，是因为如果你现在看不懂，那你就完全没有必要看下去了，往前就是高端玩家的世界了哈哈哈。

Spot Micro AI community: https://gitlab.com/custom_robots/spotmicroai

Research paper used for inverse kinematics:
`Sen, Muhammed Arif & Bakircioglu, Veli & Kalyoncu, Mete. (2017).
Inverse Kinematic Analysis Of A Quadruped Robot.
International Journal of Scientific & Technology Research. 6.`

Stanford robotics for inspiration for gait code: https://github.com/stanfordroboticsclub/StanfordQuadruped
