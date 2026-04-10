import logging
import colorlog
import os
from datetime import datetime

# Limite máximo de linhas no arquivo de log
MAX_LOG_LINES = 1000

class RotatingLineHandler(logging.FileHandler):
    """Handler que cria novo arquivo quando atinge o limite de linhas."""
    
    def __init__(self, filename, max_lines=MAX_LOG_LINES, **kwargs):
        self.max_lines = max_lines
        self.line_count = 0
        self.base_filename = filename  # Ex: logs/trading_2026-01-09.log
        self.file_index = 0
        
        # Encontra o próximo índice disponível
        self._find_current_file()
        
        # Conta linhas do arquivo atual
        if os.path.exists(self.current_filename):
            try:
                with open(self.current_filename, 'r', encoding='utf-8') as f:
                    self.line_count = sum(1 for _ in f)
            except:
                self.line_count = 0
        
        super().__init__(self.current_filename, **kwargs)
    
    def _find_current_file(self):
        """Encontra o arquivo atual ou o próximo índice disponível."""
        # Primeiro verifica o arquivo base (sem índice)
        if not os.path.exists(self.base_filename):
            self.current_filename = self.base_filename
            self.file_index = 0
            return
        
        # Conta linhas do arquivo base
        try:
            with open(self.base_filename, 'r', encoding='utf-8') as f:
                lines = sum(1 for _ in f)
            if lines < self.max_lines:
                self.current_filename = self.base_filename
                self.file_index = 0
                return
        except:
            pass
        
        # Procura arquivos com índice (_001, _002, etc)
        base, ext = os.path.splitext(self.base_filename)
        index = 1
        
        while True:
            indexed_file = f"{base}_{index:03d}{ext}"
            if not os.path.exists(indexed_file):
                # Arquivo não existe, usa ele
                self.current_filename = indexed_file
                self.file_index = index
                return
            
            # Verifica se o arquivo existente ainda tem espaço
            try:
                with open(indexed_file, 'r', encoding='utf-8') as f:
                    lines = sum(1 for _ in f)
                if lines < self.max_lines:
                    self.current_filename = indexed_file
                    self.file_index = index
                    return
            except:
                pass
            
            index += 1
            if index > 999:  # Limite de segurança
                self.current_filename = indexed_file
                self.file_index = index
                return
    
    def emit(self, record):
        """Escreve o log e cria novo arquivo se necessário."""
        super().emit(record)
        self.line_count += 1
        
        # Verifica se precisa criar novo arquivo
        if self.line_count >= self.max_lines:
            self._rotate_file()
    
    def _rotate_file(self):
        """Cria um novo arquivo de log."""
        try:
            # Fecha o arquivo atual
            self.close()
            
            # Incrementa o índice
            self.file_index += 1
            base, ext = os.path.splitext(self.base_filename)
            self.current_filename = f"{base}_{self.file_index:03d}{ext}"
            
            # Reseta contador
            self.line_count = 0
            
            # Abre o novo arquivo
            self.baseFilename = self.current_filename
            self.stream = self._open()
            
            # Log de rotação (no novo arquivo)
            self.stream.write(f"--- Arquivo de log rotacionado (anterior atingiu {self.max_lines} linhas) ---\n")
            self.line_count = 1
            
        except Exception as e:
            pass  # Ignora erros de rotação

def setup_logger(name="B3Bot"):
    """Configura um logger robusto com rotação de arquivos e saída colorida no console."""
    
    # Cria pasta de logs no diretório do projeto (não relativo ao cwd)
    # Isso garante que os logs sempre vão para b3_trading_bot/logs/
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log_dir = os.path.join(project_dir, "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Nome do arquivo de log com data
    log_file = os.path.join(log_dir, f"trading_{datetime.now().strftime('%Y-%m-%d')}.log")

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Evita duplicar handlers se a função for chamada mais de uma vez
    if logger.hasHandlers():
        return logger

    # Formato do Log
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Handler de Arquivo com rotação por linhas
    file_handler = RotatingLineHandler(log_file, max_lines=MAX_LOG_LINES, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))

    # Handler de Console (Stream Handler) com cores
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    color_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
        datefmt=date_format,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    console_handler.setFormatter(color_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
