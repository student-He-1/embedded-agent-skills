/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    main.c
  * @brief   USART1 echo on STM32F407VET6.
  *
  * PA9  = USART1_TX, PA10 = USART1_RX, 115200 8N1.
  * This board routes USART1 to the on-board J-Link CDC = COM16.
  * On reset it prints a ready banner, then echoes back every byte received.
  * Clock: HSI 16 MHz, PLL off (reliable path).
  ******************************************************************************
  */
/* USER CODE END Header */
#include "main.h"
#include <string.h>

UART_HandleTypeDef huart1;

static void USART1_GPIO_Init(void);
static void USART1_Init(void);
void SystemClock_Config(void);

void SysTick_Handler(void)
{
    HAL_IncTick();
}

int main(void)
{
    uint8_t ch;
    HAL_Init();
    SystemClock_Config();

    USART1_GPIO_Init();
    USART1_Init();

    const char banner[] =
        "\r\nUART echo ready (USART1 @115200 8N1). Type a key:\r\n";
    HAL_UART_Transmit(&huart1, (uint8_t *)banner, (uint16_t)strlen(banner), 100);

    while (1)
    {
        if (HAL_UART_Receive(&huart1, &ch, 1, HAL_MAX_DELAY) == HAL_OK)
        {
            /* Echo the byte back. */
            HAL_UART_Transmit(&huart1, &ch, 1, 100);
        }
    }
}

/* USART1 pins: PA9 TX / PA10 RX, alternate function AF7. */
static void USART1_GPIO_Init(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef g = {0};
    g.Pin = GPIO_PIN_9 | GPIO_PIN_10;
    g.Mode = GPIO_MODE_AF_PP;
    g.Pull = GPIO_PULLUP;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    g.Alternate = GPIO_AF7_USART1;
    HAL_GPIO_Init(GPIOA, &g);
}

static void USART1_Init(void)
{
    __HAL_RCC_USART1_CLK_ENABLE();

    huart1.Instance = USART1;
    huart1.Init.BaudRate = 115200;
    huart1.Init.WordLength = UART_WORDLENGTH_8B;
    huart1.Init.StopBits = UART_STOPBITS_1;
    huart1.Init.Parity = UART_PARITY_NONE;
    huart1.Init.Mode = UART_MODE_TX_RX;
    huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart1);
}

/* HSI 16 MHz, PLL off (same reliable clock path as the graduation project). */
void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
    RCC_OscInitStruct.HSIState = RCC_HSI_ON;
    RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    RCC_OscInitStruct.PLL.PLLState = RCC_PLL_NONE;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
    {
        Error_Handler();
    }

    RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK
                                | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_HSI;
    RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_SYSCLK_DIV4;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_SYSCLK_DIV2;

    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_0) != HAL_OK)
    {
        Error_Handler();
    }
}

void Error_Handler(void)
{
    __disable_irq();
    while (1)
    {
    }
}
