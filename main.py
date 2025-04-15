from ib_insync import IB

def main():
    # 创建 IB 实例并连接到 TWS 或 IB 网关
    # 请根据自己的配置修改IP、端口以及 clientId
    ib = IB()
    ib.connect('127.0.0.1', 4001, clientId=1)

    # 获取账户摘要（Account Summary）列表
    summary = ib.accountSummary()
    
    # 打印所有账户摘要信息
    print("=== 账户摘要 ===")
    for item in summary:
        print(f"Tag: {item.tag}, Value: {item.value}, Currency: {item.currency}")

    # 过滤保证金相关的数据
    margin_tags = ['InitMarginReq', 'MaintMarginReq', 'FullInitMarginReq', 'FullMaintMarginReq']
    print("\n=== 保证金相关信息 ===")
    for item in summary:
        if item.tag in margin_tags:
            print(f"{item.tag}: {item.value} {item.currency}")

    # 断开连接
    ib.disconnect()

if __name__ == '__main__':
    main()
