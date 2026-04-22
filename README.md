# Hydra Tutorial

这份教程不是泛泛介绍 Hydra，而是直接结合当前项目来讲它到底怎么工作。你看完之后，应该能回答这几个问题：

- `conf/config.yaml` 里的 `- task: l1_classifier` 为什么不是普通字符串
- `cfg.task` 为什么拿到的是一个配置对象
- `conf/task/_base.yaml` 和 `conf/task/l1_classifier.yaml` 是怎么合并的
- `compose(config_name=f"intent/{category}")` 为什么能动态加载 `conf/intent/movement.yaml`

## 1. 这个项目的配置结构

当前项目的关键文件是：

```text
conf/
├── config.yaml
├── task/
│   ├── _base.yaml
│   └── l1_classifier.yaml
└── intent/
    └── movement.yaml
main.py
```

它们分别扮演的角色是：

- `conf/config.yaml`
  这是主入口配置。程序启动时，Hydra 先从这里开始装配整个配置树。
- `conf/task/`
  这是一个 config group。这里面每个 yaml 都是一个可选的 task 配置。
- `conf/task/_base.yaml`
  这是 task 的公共基础配置。
- `conf/task/l1_classifier.yaml`
  这是具体 task，表示当前选择的是 `l1_classifier`。
- `conf/intent/movement.yaml`
  这是更细一级的业务配置，会在运行时根据类别名动态加载。

## 2. Hydra 是怎么进入程序的

`main.py` 里最关键的一行是：

```python
@hydra.main(version_base=None, config_path=_CONF_DIR, config_name="config")
```

它的含义可以拆成三部分：

- `config_path=_CONF_DIR`
  告诉 Hydra 配置根目录是项目下的 `conf/`
- `config_name="config"`
  告诉 Hydra 启动时先加载 `conf/config.yaml`
- `@hydra.main(...)`
  表示 `main(cfg)` 不是普通函数调用，而是“先让 Hydra 把配置组装好，再把结果作为 `cfg` 传进来”

所以程序真正启动时，不是你手动构造 `cfg`，而是 Hydra 自动做了这件事。

## 3. `conf/config.yaml` 在做什么

当前 `conf/config.yaml` 是：

```yaml
defaults:
  - _self_
  - task: l1_classifier

run:
  seed: 42
  n_workers: 4
```

这里最重要的是 `defaults`。

`defaults` 不是普通字段，它是 Hydra 的 Defaults List。它告诉 Hydra：

1. 先加载当前文件自己，也就是 `_self_`
2. 再去 `task` 这个配置组里选择 `l1_classifier`

也就是说，这一行：

```yaml
- task: l1_classifier
```

不是“把字符串 `l1_classifier` 赋值给 `task`”，而是：

- 去 `conf/task/` 目录下找
- 选择 `l1_classifier.yaml`
- 把该文件内容挂到最终配置的 `task` 节点下

所以这里的 `l1_classifier` 更像是“配置选择器”，不是普通业务字符串。

## 4. 为什么 `cfg.task` 不是字符串

因为 Hydra 看见：

```yaml
- task: l1_classifier
```

会去加载：

```text
conf/task/l1_classifier.yaml
```

当前这个文件内容是：

```yaml
defaults: [_base, _self_]

name: l1_classifier
pipeline: l1
categories:
  - movement
```

于是最终你在 Python 里写：

```python
task_cfg = cfg.task
```

拿到的不是：

```python
"l1_classifier"
```

而是一个子配置对象，近似于：

```yaml
task:
  categories: []
  name: l1_classifier
  pipeline: l1
  categories:
    - movement
```

更准确地说，它是 `_base.yaml` 和 `l1_classifier.yaml` 合并后的结果。

## 5. `_base.yaml` 和 `l1_classifier.yaml` 是怎么合并的

`conf/task/_base.yaml` 是：

```yaml
categories: []
```

`conf/task/l1_classifier.yaml` 是：

```yaml
defaults: [_base, _self_]

name: l1_classifier
pipeline: l1
categories:
  - movement
```

这里又出现了一个新的 `defaults`：

```yaml
defaults: [_base, _self_]
```

它的意思是：

1. 先加载 `_base.yaml`
2. 再加载当前文件 `l1_classifier.yaml`

因为后面的会覆盖前面的，所以最终：

- `_base.yaml` 先提供一个默认值：`categories: []`
- `l1_classifier.yaml` 再把它覆盖成：`categories: [movement]`

这就是 Hydra 很常见的写法：先写基础配置，再让具体配置覆盖差异部分。

## 6. `main.py` 的执行流程

当前代码主流程可以概括成这样：

```python
@hydra.main(...)
def main(cfg):
    print(cfg)
    task_cfg = cfg.task
    print(task_cfg)

    category = task_cfg.categories[0]
    intent_cfg = load_conf_dynaminic(category)
    print(intent_cfg)
```

它按顺序做了三件事：

1. 打印总配置 `cfg`
2. 取出子配置 `cfg.task`
3. 根据 `task_cfg.categories[0]` 的值，动态加载一份 intent 配置

这里最关键的是这句：

```python
category = task_cfg.categories[0]
```

在当前项目里，它拿到的是：

```python
"movement"
```

注意这次它真的是字符串。因为 `categories` 本来就是业务字段，不是 Hydra 的 Defaults List 语法。

## 7. `compose()` 为什么能加载 `conf/intent/movement.yaml`

辅助函数里有这段：

```python
def load_conf_dynaminic(category: str):
    cfg = compose(config_name=f"intent/{category}")
    container = OmegaConf.to_container(cfg, resolve=True)
    if "intent" in container:
        container = container["intent"]
    return container
```

假设 `category == "movement"`，那这一句就变成：

```python
cfg = compose(config_name="intent/movement")
```

Hydra 会根据前面已经注册好的配置根目录 `conf/`，去找：

```text
conf/intent/movement.yaml
```

所以 `compose()` 的本质是：在程序运行过程中，再临时装配一份配置。

这和 `@hydra.main(...)` 的区别是：

- `@hydra.main(...)`
  用来加载主配置入口
- `compose(...)`
  用来在运行时按条件加载额外配置

## 8. `OmegaConf.to_container(...)` 是干什么的

`compose(...)` 返回的是 `DictConfig`，不是普通 Python `dict`。

如果你想继续保持 Hydra/OmegaConf 的能力，可以直接用：

```python
cfg.category
cfg.target_count
```

但你这里写了：

```python
container = OmegaConf.to_container(cfg, resolve=True)
```

它的作用是：

- 把 `DictConfig` 转成普通 `dict` / `list`
- 如果配置里有 `${...}` 插值，先解析成最终结果

所以 `intent_cfg` 最后变成了一个普通 Python 字典，后续不用再依赖 OmegaConf。

## 9. 这一段 `if "intent" in container` 为什么存在

当前 `conf/intent/movement.yaml` 是：

```yaml
category: movement
description: "玩家对队友的移动指令：去某地、跟上、停下、转向等"
target_count: 300

dimension_weights:
  direct: 0.50
  state_sensitive: 0.25
  boundary: 0.15
  noise: 0.10
```

虽然这个文件文本里没有显式写 `intent:`，但这里是通过：

```python
compose(config_name="intent/movement")
```

来加载它的。对 Hydra 来说，这表示“从 `intent` 这个 config group 里选中 `movement`”，
所以 compose 出来的结果会先挂到顶层 `intent` 节点下。

也就是说，`OmegaConf.to_container(...)` 之后，当前项目里拿到的 `container` 大致是：

```python
{
    "intent": {
        "category": "movement",
        "description": "玩家对队友的移动指令：去某地、跟上、停下、转向等",
        "target_count": 300,
        "dimension_weights": {
            "direct": 0.5,
            "state_sensitive": 0.25,
            "boundary": 0.15,
            "noise": 0.1,
        },
    }
}
```

所以你现在这段判断通常是会触发的：

```python
if "intent" in container:
    container = container["intent"]
```

然后通过：

```python
container = container["intent"]
```

把真正的业务配置剥出来，变成：

```python
{
    "category": "movement",
    "description": "玩家对队友的移动指令：去某地、跟上、停下、转向等",
    "target_count": 300,
    "dimension_weights": {
        "direct": 0.5,
        "state_sensitive": 0.25,
        "boundary": 0.15,
        "noise": 0.1,
    },
}
```

所以这段更准确地说不是“兼容另一种配置结构”，而是在处理 Hydra compose 这个 config group 时产生的包裹层。

如果你以后改成别的加载方式，或者返回结构本来就已经是业务层字典，那这段判断才可能变成一种兼容性保护。

很多人第一次看到这里会困惑，原因就在于：

- YAML 文件内容本身没有写 `intent:`
- 但 Hydra 会根据 `intent/movement` 这个配置名，把结果挂到 `intent` 节点下

这也是“文件长什么样”和“compose 后的配置树长什么样”不完全一样的一个典型例子。

如果你手动写成另一种配置结构，例如：

```yaml
intent:
  category: movement
  description: ...
```

如果以后你把 intent 配置包了一层命名空间，这段代码还能继续工作。

## 10. 你这个项目里，哪些是“Hydra 语法”，哪些是“普通配置值”

这点很容易混，我单独拆开说。

属于 Hydra 语法的有：

- `defaults`
- `_self_`
- `- task: l1_classifier`
- `compose(config_name="intent/movement")`

属于普通业务字段的有：

- `run.seed`
- `run.n_workers`
- `task.name`
- `task.pipeline`
- `task.categories`
- `intent.category`
- `intent.target_count`

区分方法很简单：

- 如果它在控制“加载哪个配置文件”，那通常是 Hydra 机制
- 如果它在描述“业务数据是什么”，那通常只是普通配置内容

## 11. 一张心智模型图

你可以把当前项目理解成这条链路：

```text
main.py
  -> @hydra.main(..., config_name="config")
  -> 加载 conf/config.yaml
  -> defaults 里选择 task: l1_classifier
  -> 加载 conf/task/l1_classifier.yaml
  -> l1_classifier.yaml 再加载 _base.yaml
  -> 合成出 cfg.task
  -> 读取 cfg.task.categories[0] == "movement"
  -> compose("intent/movement")
  -> 加载 conf/intent/movement.yaml
```

这就是你当前项目最核心的 Hydra 工作流。

## 12. 一个最小例子

如果暂时不看项目，只看原理，可以把它缩成这样。

主配置：

```yaml
# conf/config.yaml
defaults:
  - db: mysql
```

配置组：

```yaml
# conf/db/mysql.yaml
host: localhost
port: 3306
```

Python：

```python
@hydra.main(config_path="conf", config_name="config", version_base=None)
def main(cfg):
    print(cfg.db.host)  # localhost
```

这里的：

```yaml
- db: mysql
```

和你项目里的：

```yaml
- task: l1_classifier
```

是完全同一种机制。

## 13. 当前项目里建议你这样理解

如果你只想抓住最重要的一句话，可以记这个版本：

`defaults` 里的 `task: l1_classifier` 不是在保存字符串，而是在告诉 Hydra 去 `conf/task/l1_classifier.yaml` 取配置，并把它放进 `cfg.task`。

再往后一步：

`cfg.task.categories[0]` 拿到的 `"movement"` 才是普通字符串，然后这个字符串又被你拿去拼成 `intent/movement`，再交给 `compose()` 去动态找配置文件。

## 14. 你可以继续做的几个练习

如果你想真正把 Hydra 学扎实，建议按这个顺序练：

1. 新增一个 task 配置

在 `conf/task/` 下新建一个文件，比如 `l2_classifier.yaml`，然后在里面写不同的 `pipeline` 和 `categories`，再把 `conf/config.yaml` 里的：

```yaml
- task: l1_classifier
```

改成：

```yaml
- task: l2_classifier
```

观察 `cfg.task` 怎么变化。

2. 给 `intent/` 新增一个配置

比如加一个 `conf/intent/attack.yaml`，然后把 `categories` 改成：

```yaml
categories:
  - attack
```

观察 `compose(config_name=f"intent/{category}")` 会不会自动切过去。

3. 试试命令行 override

Hydra 最常用的能力之一就是命令行覆盖配置。以后装好依赖后可以试：

```bash
python main.py task=l1_classifier
```

或者如果你新增了别的 task：

```bash
python main.py task=l2_classifier
```

这会比改 yaml 更灵活。

## 15. 总结

在这个项目里，Hydra 做了两层事情：

- 第一层，用 `defaults` 选择并合并主配置里的 `task`
- 第二层，用 `compose()` 根据业务字段 `category` 再动态加载一份 intent 配置

所以你的代码实际上是在做“主配置选择 + 运行时二次配置装配”。
