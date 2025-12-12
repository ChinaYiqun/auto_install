#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests

# 测试OPENROUTER_CONFIG配置
OPENROUTER_CONFIG = {
    "base_url": "https://openrouter.ai/api/v1",
    "model": "qwen/qwen3-vl-8b-instruct",
    "api_key": "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"
}

def test_openrouter_connection():
    """测试OPENROUTER API连接"""
    print("测试OPENROUTER API连接...")
    print(f"Base URL: {OPENROUTER_CONFIG['base_url']}")
    print(f"Model: {OPENROUTER_CONFIG['model']}")
    
    try:
        # 构建API请求URL和头部
        url = f"{OPENROUTER_CONFIG['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_CONFIG['api_key']}",
            "Content-Type": "application/json"
        }
        
        # 构建简单的测试请求体
        data = {
            "model": OPENROUTER_CONFIG['model'],
            "messages": [
                {"role": "user", "content": "Hello, world!"}
            ]
        }
        
        # 发送请求
        response = requests.post(url, headers=headers, json=data)
        
        print(f"\n响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            print("\n✓ API连接成功！")
            return True
        else:
            print(f"\n✗ API连接失败，状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"\n✗ API连接出错: {e}")
        return False

if __name__ == "__main__":
    test_openrouter_connection()
