/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : RGY running-light (water-flow) on STM32F407VET6.
  *
  * External RGY module wiring:
  *   Red    -> PA0
  *   Yellow -> PA1
  *   Green  -> PA3
  *
  * The light moves R -> Y -> G in a loop (one LED on at a time).
  * Default polarity is active HIGH (common-cathode module, matching the
  * graduation-project RGB module). If your module is common-anode (active
  * LOW), swap LED_LEVEL_ON / LED_LEVEL_OFF below.
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private defines -----------------------------------------------------------*/
/* Polarity: active high by default. For active-low hardware, set
   LED_LEVEL_ON=GPIO_PIN_RESET and LED_LEVEL_OFF=GPIO_PIN_SET. */
#define LED_LEVEL_ON   GPIO_PIN_SET
#define LED_LEVEL_OFF  GPIO_PIN_RESET

#define LED_STEP_MS    300U   /* time each color stays on */

/* RGY LED pin map, in flow order: Red, Yellow, Green. */
typedef struct
{
    GPIO_TypeDef *port;
    uint16_t pin;
} led_t;

static const led_t LEDS[] = {
    { GPIOA, GPIO_PIN_0 },  /* Red    */
    { GPIOA, GPIO_PIN_1 },  /* Yellow */
    { GPIOA, GPIO_PIN_3 },  /* Green  */
};
#define LED_COUNT  (sizeof(LEDS) / sizeof(LEDS[0]))

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void LED_GPIO_Init(void);
static void LED_All_Off(void);
static void LED_On(uint8_t idx);

/* USER CODE BEGIN 0 */

/* SysTick handler: HAL time base. Overrides the weak alias in startup. */
void SysTick_Handler(void)
{
    HAL_IncTick();
}

/* USER CODE END 0 */

int main(void)
{
    HAL_Init();
    SystemClock_Config();

    LED_GPIO_Init();
    LED_All_Off();

    uint8_t idx = 0;
    while (1)
    {
        LED_On(idx);
        HAL_Delay(LED_STEP_MS);
        LED_All_Off();
        idx = (uint8_t)((idx + 1U) % LED_COUNT);
    }
}

/* Initialize the three LED pins as push-pull outputs. */
static void LED_GPIO_Init(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef gi = {0};
    gi.Mode = GPIO_MODE_OUTPUT_PP;
    gi.Pull = GPIO_NOPULL;
    gi.Speed = GPIO_SPEED_FREQ_LOW;
    for (uint8_t i = 0; i < LED_COUNT; i++)
    {
        gi.Pin = LEDS[i].pin;
        HAL_GPIO_Init(LEDS[i].port, &gi);
        HAL_GPIO_WritePin(LEDS[i].port, LEDS[i].pin, LED_LEVEL_OFF);
    }
}

static void LED_All_Off(void)
{
    for (uint8_t i = 0; i < LED_COUNT; i++)
    {
        HAL_GPIO_WritePin(LEDS[i].port, LEDS[i].pin, LED_LEVEL_OFF);
    }
}

static void LED_On(uint8_t idx)
{
    if (idx < LED_COUNT)
    {
        HAL_GPIO_WritePin(LEDS[idx].port, LEDS[idx].pin, LED_LEVEL_ON);
    }
}

/**
  * @brief System Clock Configuration
  * @retval None
  *
  * Uses the internal 16 MHz HSI with the PLL OFF (same reliable clock path as
  * the graduation project): SYSCLK=16 MHz, AHB=16 MHz, APB1=4 MHz (/4),
  * APB2=8 MHz (/2), Flash latency = 0 WS.
  *
  * HSE 8 MHz + PLL 168 MHz is NOT used here because HSE is unverified on this
  * board; the running-light timing is clock-independent anyway.
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

/**
  * @brief  This function is executed in case of error occurrence.
  */
void Error_Handler(void)
{
    __disable_irq();
    while (1)
    {
    }
}
