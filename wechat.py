"""Reserved compatibility interface; external messaging is disabled."""


def send2wechat(AgentId, Secret, CompanyId, message):
    raise RuntimeError("WeChat delivery is disabled. Use the local OA inbox.")


if __name__ == "__main__":
    print("WeChat delivery is disabled. No message was sent.")
