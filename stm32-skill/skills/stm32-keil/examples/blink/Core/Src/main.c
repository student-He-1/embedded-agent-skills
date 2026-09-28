/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Blink the on-board user LED (PA1, active low) on STM32F407VET6.
  *
  * Minimal HAL project: HSI 16 MHz, PLL off (the verified-reliable clock path
  * on this board). Validates the loop: static check -> build -> flash -> LED.
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);

/* USER CODE BEGIN 0 */

/* SysTick handler: HAL time base. Overrides the weak alias in startup. */
void SysTick_Handler(void)
{
    HAL_IncTick();
}

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{
    /* Reset of all peripherals, initialize the Flash interface and SysTick. */
    HAL_Init();

    /* Configure the system clock (HSI 16 MHz, PLL off). */
    SystemClock_Config();

    /* Enable GPIOA clock and configure PA1 as push-pull output. */
    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin = GPIO_PIN_1;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

    /* LED D2 is active low: start with it off (PA1 high). */
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_1, GPIO_PIN_SET);

    /* Infinite loop: toggle PA1 every 500 ms -> 1 s period. */
    while (1)
    {
        HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_1);
        HAL_Delay(500);
    }
}

/**
  * @brief System Clock Configuration
  * @retval None
  *
  * HSI internal 16 MHz, PLL OFF: SYSCLK/AHB = 16 MHz, APB1 = 4 MHz (/4),
  * APB2 = 8 MHz (/2), flash latency = 0 WS. HSE 8 MHz + PLL 168 MHz is not
  * used because HSE is unverified on this board.
  */
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

/* USER CODE BEGIN 4 */

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
    /* HAL error: stay here with interrupts off. */
    __disable_irq();
    while (1)
    {
    }
}
