import { NextRequest, NextResponse } from 'next/server';

interface ContactForm {
  name: string;
  email: string;
  message: string;
}

export async function POST(request: NextRequest) {
  const body: ContactForm = await request.json();
  
  // 这里实际应该保存到数据库或发送邮件
  console.log('收到联系表单:', body);
  
  // 模拟处理
  if (!body.name || !body.email || !body.message) {
    return NextResponse.json(
      { error: '请填写所有字段' },
      { status: 400 }
    );
  }
  
  return NextResponse.json(
    { message: '感谢您的留言！我们会尽快与您联系。' },
    { status: 201 }
  );
}
