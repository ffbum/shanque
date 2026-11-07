import { App, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import dayjs from 'dayjs';
import 'dayjs/locale/zh-cn';
import type { ReactNode } from 'react';

dayjs.locale('zh-cn');
export function rootContainer(container: ReactNode) {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#176951',
          colorInfo: '#176951',
          colorSuccess: '#39765b',
          colorError: '#b34b48',
          colorWarning: '#a77932',
          colorBgLayout: '#f5f7f4',
          colorText: '#1d302e',
          borderRadius: 6,
          fontFamily: 'Inter, "Segoe UI", "Microsoft YaHei", sans-serif',
        },
      }}
    >
      <App>{container}</App>
    </ConfigProvider>
  );
}
