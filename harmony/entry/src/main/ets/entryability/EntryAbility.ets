import { AbilityConstant, ConfigurationConstant, UIAbility, Want } from '@kit.AbilityKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { window } from '@kit.ArkUI';
import { backgroundTaskManager } from '@kit.BackgroundTasksKit';

const DOMAIN = 0x0000;
const TAG = 'EntryAbility';

export default class EntryAbility extends UIAbility {
  private backgroundTaskStarted_: boolean = false;

  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    try {
      this.context.getApplicationContext().setColorMode(ConfigurationConstant.ColorMode.COLOR_MODE_NOT_SET);
    } catch {
      hilog.error(DOMAIN, TAG, 'Failed to set colorMode');
    }
    hilog.info(DOMAIN, TAG, '%{public}s', 'Ability onCreate');
  }

  onDestroy(): void {
    this.stopBackgroundTask_();
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
    this.stopBackgroundTask_();
  }

  onBackground(): void {
    hilog.info(DOMAIN, TAG, '%{public}s', 'Ability onBackground');
    this.startBackgroundTask_();
  }

  private startBackgroundTask_(): void {
    if (this.backgroundTaskStarted_) return;
    try {
      backgroundTaskManager.startBackgroundRunning(
        this.context,
        backgroundTaskManager.BackgroundMode.AUDIO_PLAYBACK,
        () => {
          // 续期回调 - 音频播放任务通常不需要续期
        }
      );
      this.backgroundTaskStarted_ = true;
      hilog.info(DOMAIN, TAG, '%{public}s', 'Background task started');
    } catch {
      hilog.error(DOMAIN, TAG, 'startBackgroundRunning failed');
      this.backgroundTaskStarted_ = false;
    }
  }

  private stopBackgroundTask_(): void {
    if (!this.backgroundTaskStarted_) return;
    try {
      backgroundTaskManager.stopBackgroundRunning(this.context);
      this.backgroundTaskStarted_ = false;
      hilog.info(DOMAIN, TAG, '%{public}s', 'Background task stopped');
    } catch {
      hilog.error(DOMAIN, TAG, 'stopBackgroundRunning failed');
      this.backgroundTaskStarted_ = false;
    }
  }
}