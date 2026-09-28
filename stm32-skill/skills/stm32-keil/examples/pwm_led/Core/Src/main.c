/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    main.c
  * @brief   PWM breathing LED on STM32F407VET6.
  *
  * Drives the on-board user LED D2 on PA1 = TIM2_CH2 (AF1) with a hardware PWM
  * signal that ramps the duty cycle up and down (breathing effect).
  *
  * Note: D2 is active LOW, so duty cycle inverses the apparent brightness, but
  * the ramp is still a smooth breathing fade.
  *
  * Clock: HSI 16 MHz, PLL off. TIM2 is on APB1; with APB1=/4 the timer clock
  * is 8 MHz. PSC=7 -> 1 MHz tick; ARR=999 -> 1 kHz PWM.
  ******************************************************************************
  */
/* USER CODE END Header */
#include "main.h"

TIM_HandleTypeDef htim2;

static void PWM_GPIO_Init(void);
static void TIM2_Init(void);
void SystemClock_Config(void);

#define PERIOD 1000U   /* ARR+1; duty ranges 0..PERIOD-1 */

void SysTick_Handler(void)
{
    HAL_IncTick();
}

int main(void)
{
    uint32_t duty = 0;
    int32_t step = 8;

    HAL_Init();
    SystemClock_Config();

    PWM_GPIO_Init();
    TIM2_Init();
    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_2);

    while (1)
    {
        __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, duty);
        duty = (uint32_t)((int32_t)duty + step);
        if (duty >= PERIOD) { duty = PERIOD - 1U; step = -8; }
        else if ((int32_t)duty <= 0) { duty = 0; step = 8; }
        HAL_Delay(5);
    }
}

/* PA1 = TIM2_CH2, alternate function AF1. */
static void PWM_GPIO_Init(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef g = {0};
    g.Pin = GPIO_PIN_1;
    g.Mode = GPIO_MODE_AF_PP;
    g.Pull = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    g.Alternate = GPIO_AF1_TIM2;
    HAL_GPIO_Init(GPIOA, &g);
}

static void TIM2_Init(void)
{
    TIM_OC_InitTypeDef oc = {0};

    __HAL_RCC_TIM2_CLK_ENABLE();

    htim2.Instance = TIM2;
    htim2.Init.Prescaler = 8 - 1U;                 /* 8 MHz / 8 = 1 MHz tick */
    htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim2.Init.Period = PERIOD - 1U;               /* 1 MHz / 1000 = 1 kHz */
    htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
    HAL_TIM_Base_Init(&htim2);

    oc.OCMode = TIM_OCMODE_PWM1;
    oc.Pulse = 0;
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    oc.OCFastMode = TIM_OCFAST_DISABLE;
    HAL_TIM_PWM_ConfigChannel(&htim2, &oc, TIM_CHANNEL_2);
}

/* HSI 16 MHz, PLL off. */
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
