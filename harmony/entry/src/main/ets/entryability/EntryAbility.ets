import { AbilityConstant, ConfigurationConstant, UIAbility, Want, common } from '@kit.AbilityKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { window } from '@kit.ArkUI';
import rpc from '@ohos.rpc';
import { setServiceRemote } from '../bridge/AudioServiceProxy';

const DOMAIN = 0x0000;
const TAG = 'EntryAbility';

export default class EntryAbility extends UIAbility {
  private connection_: number = 0;

  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    try {
      this.context.getApplicationContext().setColorMode(ConfigurationConstant.ColorMode.COLOR_MODE_NOT_SET);
    } catch {
      hilog.error(DOMAIN, TAG, 'Failed to set colorMode');
    }
    hilog.info(DOMAIN, TAG, '%{public}s', 'Ability onCreate');
    this.connectService_();
  }

  onDestroy(): void {
    this.disconnectService_();
    hilog.info(DOMAIN, TAG, '%{public}s', 'Ability onDestroy');
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    hilog.info(DOMAIN, TAG, '%{public}s', 'Ability onWindowStageCreate');

    windowStage.loadContent('pages/Index', (err) => {
      if (err.code) {
        hilog.error(DOMAIN, TAG, 'Failed to load the content. Cause: %{public}s', JSON.stringify(err));
        return;
      }
      hilog.info(DOMAIN, TAG, '%{public}s', 'Succeeded in loading the content.');
    });
  }

  onWindowStageDestroy(): void {
    hilog.info(DOMAIN, TAG, '%{public}s', 'Ability onWindowStageDestroy');
  }

  onForeground(): void {
    hilog.info(DOMAIN, TAG, '%{public}s', 'Ability onForeground');
  }

  onBackground(): void {
    // 后台任务由 AudioServiceAbility 接管，此处不需要手动处理
    hilog.info(DOMAIN, TAG, '%{public}s', 'Ability onBackground');
  }

  /** 连接到 AudioServiceAbility */
  private connectService_(): void {
    const want: Want = {
      bundleName: this.context.abilityInfo.bundleName,
      abilityName: 'AudioServiceAbility'
    };
    const connectOptions: common.ConnectOptions = {
      onConnect: (elementName, remote: rpc.IRemoteObject): void => {
        hilog.info(DOMAIN, TAG, '%{public}s', 'AudioService connected');
        setServiceRemote(remote);
      },
      onDisconnect: (elementName): void => {
        hilog.info(DOMAIN, TAG, '%{public}s', 'AudioService disconnected');
      },
      onFailed: (code: number): void => {
        hilog.error(DOMAIN, TAG, 'AudioService connect failed: %{public}d', code);
      }
    };
    try {
      this.connection_ = this.context.connectServiceExtensionAbility(want, connectOptions);
    } catch (_e) {
      hilog.error(DOMAIN, TAG, 'connect service failed');
    }
  }

  /** 断开与 AudioServiceAbility 的连接 */
  private disconnectService_(): void {
    if (this.connection_ > 0) {
      try {
        this.context.disconnectServiceExtensionAbility(this.connection_);
      } catch (_e) { /* ignore */ }
      this.connection_ = 0;
    }
  }
}