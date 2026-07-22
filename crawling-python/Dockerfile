# ==================== Python 크롤링 서비스 이미지 ====================

FROM python:3.11-slim

WORKDIR /app

# ✅ [추가] KoNLPy(JPype) 구동을 위한 JRE 설치
# KoNLPy는 내부적으로 Java 형태소 분석기를 JPype로 호출하므로 JVM이 반드시 필요합니다.
RUN apt-get update && \
    apt-get install -y --no-install-recommends default-jre-headless && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ✅ [추가] JAVA_HOME 환경변수 설정
# JPype가 libjvm.so 위치를 찾을 수 있도록 명시적으로 지정합니다.
ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV PATH=$JAVA_HOME/bin:$PATH

# 의존성 설치 (requirements.txt)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 프로젝트 소스 코드 복사
COPY . .

EXPOSE 5000

CMD ["python", "-u", "main.py"]