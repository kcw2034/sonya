from typing import Any, Optional
from google import genai
from google.genai import types

class ThinGeminiAgent:
    """
    프레임워크의 개입을 최소화하고, 기본 SDK로 파라미터를 패스스루하는 경량 에이전트
    """
    def __init__(self, model_name: str = "gemini-2.5-pro", system_message: Optional[str] = None):
        self.client = genai.Client() # 기본 SDK 클라이언트
        self.model_name = model_name
        self.system_message = system_message

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        prompt: 프레임워크가 요구하는 필수 규격 (타입 힌트로 명시)
        kwargs: 기본 SDK로 그대로 전달될 추가 파라미터들 (패스스루)
        """
        # 1. 프레임워크 필수 로직: 메시지 규격화
        contents = prompt 

        # 2. Config 조립: 프레임워크 기본값 + kwargs 병합
        config_args = {}
        if self.system_message:
            config_args["system_instruction"] = self.system_message
            
        # 사용자가 전달한 모든 추가 파라미터(kwargs)를 그대로 덮어씌웁니다.
        # 프레임워크는 kwargs 안에 무엇이 있는지 검사(Validation)하지 않습니다.
        config_args.update(kwargs)

        # 3. 원본 SDK 호출: 조립된 config_args를 언패킹하여 전달
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(**config_args)
        )
        
        return response.text