# coding:utf-8

import hydra
from pathlib import Path
from hydra import compose
from omegaconf import DictConfig, OmegaConf

# `conf/` 是整个项目的 Hydra 配置根目录。
# 这里把它算成绝对路径，交给 `@hydra.main(...)` 使用。
# 这样无论脚本从哪里启动，Hydra 都能稳定找到配置文件。
_CONF_DIR = str(Path(__file__).absolute().parent / "conf")

def load_conf_dynaminic(category: str):
    # 这个函数按“类别名”动态加载一份 intent 配置。
    # 比如传入 "movement"，实际会去找：
    #   conf/intent/movement.yaml
    #
    # 这里没有重新指定 config_path，是因为外层的 `@hydra.main(...)`
    # 已经把 `conf/` 注册进 Hydra 的配置搜索路径里了。
    # 所以 `compose(config_name="intent/movement")` 可以直接按相对配置名查找。
    cfg = compose(config_name=f"intent/{category}")

    # `compose(...)` 返回的是 OmegaConf/DictConfig 对象。
    # 例如 movement.yaml 的内容大致会变成：
    # {
    #   "category": "movement",
    #   "description": "...",
    #   "target_count": 300,
    #   ...
    # }
    #
    # `to_container(..., resolve=True)` 的作用：
    # 1. 把 DictConfig 转成普通 Python dict/list
    # 2. 如果配置里有插值 `${...}`，会先解析成最终值
    container = OmegaConf.to_container(cfg, resolve=True)

    # 这一段是兼容性写法。
    # 某些 Hydra 配置会长这样：
    #   intent:
    #     category: movement
    #     ...
    # 如果最外层有个 `intent` 包裹，就只把里面真正的业务配置取出来。
    #
    # 你当前的 movement.yaml 顶层并没有 `intent:` 这一层，
    # 所以这里一般不会进入 if，`container` 会原样返回。
    if "intent" in container:
        container = container["intent"]
    return container

@hydra.main(version_base=None, config_path=_CONF_DIR, config_name="config")
def main(cfg: DictConfig):
    # `@hydra.main(...)` 会在程序启动时自动加载：
    #   conf/config.yaml
    #
    # 然后把最终合成后的总配置对象作为参数 `cfg` 传进来。
    # 注意这里的 `cfg` 不是普通 dict，而是 DictConfig。
    #
    # 按你当前的 conf/config.yaml：
    #   defaults:
    #     - _self_
    #     - task: l1_classifier
    #
    # Hydra 会继续去加载：
    #   conf/task/l1_classifier.yaml
    #
    # 而 `l1_classifier.yaml` 里又有：
    #   defaults: [_self_, _base]
    #
    # 所以最终 `cfg` 其实是多份配置 merge 后的结果。
    #
    # 这里打印的是“整个主配置对象”，而不是单纯的 config.yaml 原始文本。
    print(cfg)
    
    # `cfg.task` 对应的是 defaults 里这句：
    #   - task: l1_classifier
    #
    # 它的含义不是把字符串 "l1_classifier" 塞给 `cfg.task`，
    # 而是“去 task 这个配置组里选择 l1_classifier.yaml，
    # 再把该文件内容挂到 `task` 节点下”。
    #
    # 所以这里取到的是一个子配置对象，而不是字符串。
    task_cfg = cfg.task

    # 这里打印的是 `conf/task/l1_classifier.yaml`
    # 与 `conf/task/_base.yaml` 合并之后得到的 task 配置。
    # 按当前项目，大致会包含：
    #   name: l1_classifier
    #   pipeline: l1
    #   categories:
    #     - movement
    print(task_cfg)

    # `categories` 是一个列表，这里先取第一个类别。
    # 结合当前配置，拿到的值就是字符串：
    #   "movement"
    #
    # 这个字符串现在只是“配置名 / 类别名”，
    # 接下来会把它拼进 `intent/{category}`，用于动态加载对应 intent 配置。
    category = task_cfg.categories[0]

    # 调用上面的辅助函数，等价于加载：
    #   conf/intent/movement.yaml
    #
    # 返回值 `intent_cfg` 已经是普通 Python dict 了，
    # 不再是 DictConfig。
    intent_cfg = load_conf_dynaminic(category)

    # 这里打印的是 movement intent 的配置内容，例如：
    # {
    #   "category": "movement",
    #   "description": "...",
    #   "target_count": 300,
    #   "dimension_weights": {...}
    # }
    print(intent_cfg)

if __name__ == "__main__":
    # 直接运行脚本时，从这里进入。
    # `main()` 实际会先经过 Hydra 装饰器包装，
    # 再由 Hydra 完成配置加载后调用真正的主逻辑。
    main()
